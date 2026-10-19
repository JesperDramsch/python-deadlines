"""Tests that conference text reaches the site's JavaScript and HTML attributes escaped.

Liquid pastes a value into a template verbatim. A conference name or place with
an apostrophe or quote ("Abidjan, Côte d'Ivoire") inside a quoted JavaScript
string ends the string early, and the whole inline script fails to parse: on the
front page that is every conference. Free-text fields must reach JavaScript
through ``jsonify``, which emits a complete, escaped string literal. Inside an
HTML tag a ``"`` ends the attribute value instead, so free text there goes
through ``escape``, or ``url_encode`` when it is part of a URL.

The checker follows a field into include parameters (``conf_name=conf.conference``)
and into variables set from it with ``assign`` or ``for`` in the same file. A value
that travels any other way, such as through ``capture`` or a variable set in
another file, gets past it.
"""

import re
import sys
from pathlib import Path
from typing import get_args

import pytest
from pydantic import HttpUrl

sys.path.append(str(Path(__file__).parent.parent / "utils"))

from tidy_conf.schema import Conference

ROOT = Path(__file__).parent.parent

TEMPLATE_DIRS = ["_includes", "_layouts", "_pages", "_years"]

# Fields whose values the schema pins to a quote-free format: numbers, dates,
# deadlines, IANA zone names and type codes. Every other field is free text,
# including fields added to the schema later.
FORMATTED_FIELDS = {
    "year",
    "cfp",
    "cfp_ext",
    "workshop_deadline",
    "tutorial_deadline",
    "timezone",
    "start",
    "end",
    "sub",
}
FREE_TEXT_FIELDS = set(Conference.model_fields) - FORMATTED_FIELDS

# Fields the schema validates as URLs. Pydantic percent-encodes quotes and spaces
# in them, so they are safe in a double-quoted HTML attribute. A ' survives, so in
# JavaScript they still need jsonify.
URL_FIELDS = {
    name
    for name, field in Conference.model_fields.items()
    if HttpUrl in (field.annotation, *get_args(field.annotation))
}
ATTRIBUTE_FIELDS = FREE_TEXT_FIELDS - URL_FIELDS

# Filters whose output is safe in JavaScript: a full string literal, or [a-z0-9-].
SCRIPT_FILTERS = {"jsonify", "slugify"}
# Filters whose output holds no quote, for HTML attributes.
ATTRIBUTE_FILTERS = {"escape", "escape_once", "xml_escape", "url_encode", "cgi_escape", "slugify"}

SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script\b[^>]*>", re.DOTALL | re.IGNORECASE)
LIQUID = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
OUTPUT_TAG = re.compile(r"\{\{-?(.*?)-?\}\}", re.DOTALL)
INCLUDE = re.compile(r"\{%-?\s*include(?:_cached)?\s+(\S+)(.*?)-?%\}", re.DOTALL)
INCLUDE_PARAMETER = re.compile(r"(\w+)\s*=\s*([\w.\[\]]+)")
VARIABLE = re.compile(r"\{%-?\s*(?:assign\s+(\w+)\s*=|for\s+(\w+)\s+in)(.*?)-?%\}", re.DOTALL)


def template_files():
    """List the templates Jekyll renders with Liquid."""
    files = [ROOT / "index.html"]
    for directory in TEMPLATE_DIRS:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.suffix in {".html", ".js", ".md"})
    return sorted(path for path in files if path.is_file())


def include_name(path):
    """Return the name an include tag uses for the file, or None outside _includes."""
    if "_includes" not in path.parts:
        return None
    return "/".join(path.parts[path.parts.index("_includes") + 1 :])


def field_pattern(fields, variables=()):
    """Match a reference to one of the fields, or to a variable that holds one."""
    alternatives = [r"\.(?:" + "|".join(sorted(fields)) + r")\b"]
    if variables:
        alternatives.append(r"(?<![\w.])(?:" + "|".join(sorted(variables)) + r")\b")
    return re.compile("|".join(alternatives))


def include_parameters(templates, fields):
    """Map each include to the parameters its callers fill with one of the fields."""
    pattern = field_pattern(fields)
    parameters = {}
    for _, text in templates:
        for include in INCLUDE.finditer(text):
            for name, value in INCLUDE_PARAMETER.findall(include.group(2)):
                if pattern.search(value):
                    parameters.setdefault(include.group(1), set()).add(name)
    return parameters


def file_pattern(path, text, fields, parameters):
    """Match the fields in one template, with its include parameters and the variables set from them."""
    fields = fields | parameters.get(include_name(path), set())
    variables = set()
    # A second pass picks up a variable set from a variable set further down.
    for _ in range(2):
        pattern = field_pattern(fields, variables)
        for variable in VARIABLE.finditer(text):
            value, *filters = variable.group(3).split("|")
            if pattern.search(value) and "slugify" not in (part.split(":")[0].strip() for part in filters):
                variables.add(variable.group(1) or variable.group(2))
    return field_pattern(fields, variables)


def script_regions(path, text):
    """Yield (offset, source) for each stretch of a template that is JavaScript or JSON."""
    if path.suffix == ".js":
        yield 0, text
        return
    for match in SCRIPT.finditer(text):
        yield match.start(1), match.group(1)


def attribute_tags(path, text):
    """Yield the Liquid output tags that sit inside an HTML tag, outside scripts."""
    if path.suffix == ".js":
        return
    html = SCRIPT.sub(lambda match: " " * len(match.group(0)), text)
    # Blank out Liquid, so the > in {% if a > b %} is not read as the end of a tag.
    markup = LIQUID.sub(lambda match: " " * len(match.group(0)), html)
    for tag in OUTPUT_TAG.finditer(html):
        if markup.rfind("<", 0, tag.start()) > markup.rfind(">", 0, tag.start()):
            yield tag


def filters_after_field(expression, pattern):
    """Return the filters applied after the last free-text field in a Liquid expression, or None if it has none."""
    fields = list(pattern.finditer(expression))
    if not fields:
        return None
    return [part.split(":")[0].strip() for part in expression[fields[-1].end() :].split("|")[1:]]


def location(path, text, offset, tag):
    """Format where a Liquid output tag sits in a template."""
    line = text.count("\n", 0, offset) + 1
    return f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}:{line}: {tag}"


def violations(path, text, script_parameters=None, attribute_parameters=None):
    """Return one message per Liquid output tag that can break the script or HTML tag around it."""
    found = []
    pattern = file_pattern(path, text, FREE_TEXT_FIELDS, script_parameters or {})
    for offset, source in script_regions(path, text):
        for tag in OUTPUT_TAG.finditer(source):
            where = location(path, text, offset + tag.start(), tag.group(0))
            filters = filters_after_field(tag.group(1), pattern)
            if filters is not None and (not filters or filters[-1] not in SCRIPT_FILTERS):
                found.append(f"{where} (free text needs '| jsonify')")
            elif tag.group(1).split("|")[-1].strip() == "jsonify":
                before = source[tag.start() - 1 : tag.start()]
                after = source[tag.end() : tag.end() + 1]
                if before in {"'", '"', "`"} or after in {"'", '"', "`"}:
                    found.append(f"{where} (jsonify emits its own quotes)")

    pattern = file_pattern(path, text, ATTRIBUTE_FIELDS, attribute_parameters or {})
    for tag in attribute_tags(path, text):
        filters = filters_after_field(tag.group(1), pattern)
        if filters is not None and not ATTRIBUTE_FILTERS.intersection(filters):
            where = location(path, text, tag.start(), tag.group(0))
            found.append(f"{where} (free text in an HTML tag needs '| escape' or '| url_encode')")
    return found


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ("<script>var p = '{{ conf.place }}';</script>", 1),
        ('<script>var n = "{{conf.conference}} {{conf.year}}";</script>', 1),
        ("<script>var t = '{{ page.conference | append: page.year }}';</script>", 1),
        ("<script>var l = '{{ conf.link }}';</script>", 1),
        ("<script>var p = '{{ conf.place | jsonify }}';</script>", 1),
        ("<script>var p = {{ conf.place | jsonify }};</script>", 0),
        ("<script>var t = {{ page.conference | append: ' ' | append: page.year | jsonify }};</script>", 0),
        ("<script>var id = '{{ conf.conference | slugify: \"latin\" }}-{{ conf.year }}';</script>", 0),
        ("<script>var d = Date.parse('{{ conf.start }}'); var tz = '{{ conf.timezone }}';</script>", 0),
        ('<div data-conf-name="{{ conf.conference }}"></div>', 1),
        ('<a href="https://maps.google.com/?q={{ include.place }}">', 1),
        ('<meta content="{{ page.conference | escape }} in {{ page.place }}">', 1),
        ('<a href="https://twitter.com/{{ conf.twitter }}">', 1),
        ('<div {% if conf.note %}title="{{ conf.note }}"{% endif %}>', 1),
        ('{% for place in conf.extra_places %}<a href="?q={{ place }}">{{ place }}</a>{% endfor %}', 1),
        ('{% assign name = conf.conference | strip %}<div title="{{ name }}"></div>', 1),
        ('{% assign id = conf.conference | slugify %}<script>var i = "{{ id }}";</script>', 0),
        ('<div data-conf-name="{{ conf.conference | escape }}"></div>', 0),
        ('<a href="?q={{ page.place | url_encode }}">', 0),
        ('<a href="mailto:?subject={{ page.conference | url_encode | replace: "+", "%20" }}">', 0),
        ('<a href="{{ conf.link }}">{{ conf.conference }} {{ conf.year }}</a>', 0),
        ("{% if a > b %}<p>{{ conf.place }}</p>{% endif %}", 0),
    ],
)
def test_checker_flags_unescaped_free_text(tmp_path, snippet, expected):
    """The checker flags free text in scripts and HTML tags unless a matching filter escapes it."""
    path = tmp_path / "page.html"

    assert len(violations(path, f"<p>{{{{ conf.place }}}}</p>\n{snippet}\n")) == expected


def test_checker_follows_include_parameters(tmp_path):
    """A field passed into an include under another name is still free text inside the include."""
    caller = (tmp_path / "index.html", "{% include bar.html conf_name=conf.conference conf_id=conf_id %}")
    include = tmp_path / "_includes" / "bar.html"
    text = '<div data-conf-name="{{ include.conf_name }}" data-conf-id="{{ include.conf_id }}"></div>'

    assert len(violations(include, text, attribute_parameters=include_parameters([caller], ATTRIBUTE_FIELDS))) == 1


def test_checker_reads_templates():
    """The checker finds the jsonify'd conference data the site already injects."""
    head = ROOT / "_includes" / "head.html"
    tags = [
        tag.group(1)
        for _, source in script_regions(head, head.read_text(encoding="utf-8"))
        for tag in OUTPUT_TAG.finditer(source)
    ]

    assert any("conf.place" in tag and "jsonify" in tag for tag in tags)


def test_checker_reads_attributes():
    """The checker finds the conference names the front page puts into data attributes."""
    index = ROOT / "index.html"
    tags = [tag.group(1) for tag in attribute_tags(index, index.read_text(encoding="utf-8"))]

    assert any("conf.conference" in tag for tag in tags)


def test_free_text_reaches_templates_escaped():
    """Conference text in scripts goes through jsonify, and in HTML tags through escape or url_encode."""
    templates = [(path, path.read_text(encoding="utf-8")) for path in template_files()]
    script_parameters = include_parameters(templates, FREE_TEXT_FIELDS)
    attribute_parameters = include_parameters(templates, ATTRIBUTE_FIELDS)
    found = [
        message
        for path, text in templates
        for message in violations(path, text, script_parameters, attribute_parameters)
    ]

    assert not found, "Unescaped Liquid output:\n" + "\n".join(found)
