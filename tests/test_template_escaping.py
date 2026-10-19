"""Tests that conference text reaches the site's JavaScript escaped.

Liquid pastes a value into a template verbatim. A conference name or place with
an apostrophe or quote ("Abidjan, Côte d'Ivoire") inside a quoted JavaScript
string ends the string early, and the whole inline script fails to parse: on the
front page that is every conference. Free-text fields must reach JavaScript
through ``jsonify``, which emits a complete, escaped string literal.
"""

import re
import sys
from pathlib import Path

import pytest

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

# Filters whose output is safe in JavaScript: a full string literal, or [a-z0-9-].
SAFE_FILTERS = {"jsonify", "slugify"}

SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
OUTPUT_TAG = re.compile(r"\{\{-?(.*?)-?\}\}", re.DOTALL)
FIELD_REF = re.compile(r"\.(" + "|".join(sorted(FREE_TEXT_FIELDS)) + r")\b")


def template_files():
    """List the templates Jekyll renders with Liquid."""
    files = [ROOT / "index.html"]
    for directory in TEMPLATE_DIRS:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.suffix in {".html", ".js", ".md"})
    return sorted(path for path in files if path.is_file())


def script_regions(path, text):
    """Yield (offset, source) for each stretch of a template that is JavaScript or JSON."""
    if path.suffix == ".js":
        yield 0, text
        return
    for match in SCRIPT.finditer(text):
        yield match.start(1), match.group(1)


def violations(path, text):
    """Return one message per Liquid output tag that can break the script around it."""
    found = []
    for offset, source in script_regions(path, text):
        for tag in OUTPUT_TAG.finditer(source):
            expression = tag.group(1)
            filters = [part.split(":")[0].strip() for part in expression.split("|")[1:]]
            last_filter = filters[-1] if filters else None
            line = text.count("\n", 0, offset + tag.start()) + 1
            where = f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}:{line}: {tag.group(0)}"

            if FIELD_REF.search(expression) and last_filter not in SAFE_FILTERS:
                found.append(f"{where} (free text needs '| jsonify')")
            elif last_filter == "jsonify":
                before = source[tag.start() - 1 : tag.start()]
                after = source[tag.end() : tag.end() + 1]
                if before in {"'", '"', "`"} or after in {"'", '"', "`"}:
                    found.append(f"{where} (jsonify emits its own quotes)")
    return found


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ("var p = '{{ conf.place }}';", 1),
        ('var n = "{{conf.conference}} {{conf.year}}";', 1),
        ("var t = '{{ page.conference | append: page.year }}';", 1),
        ("var l = '{{ conf.link }}';", 1),
        ("var p = '{{ conf.place | jsonify }}';", 1),
        ("var p = {{ conf.place | jsonify }};", 0),
        ("var t = {{ page.conference | append: ' ' | append: page.year | jsonify }};", 0),
        ("var id = '{{ conf.conference | slugify: \"latin\" }}-{{ conf.year }}';", 0),
        ("var d = Date.parse('{{ conf.start }}'); var tz = '{{ conf.timezone }}';", 0),
    ],
)
def test_checker_flags_unescaped_free_text(tmp_path, snippet, expected):
    """The checker flags free text in JavaScript unless jsonify or slugify formats it."""
    path = tmp_path / "page.html"
    text = f"<p>{{{{ conf.place }}}}</p>\n<script>\n{snippet}\n</script>\n"

    assert len(violations(path, text)) == expected


def test_checker_reads_templates():
    """The checker finds the jsonify'd conference data the site already injects."""
    head = ROOT / "_includes" / "head.html"
    tags = [
        tag.group(1)
        for _, source in script_regions(head, head.read_text(encoding="utf-8"))
        for tag in OUTPUT_TAG.finditer(source)
    ]

    assert any("conf.place" in tag and "jsonify" in tag for tag in tags)


def test_free_text_reaches_javascript_escaped():
    """Conference names, places, links and notes in scripts go through jsonify."""
    found = [message for path in template_files() for message in violations(path, path.read_text(encoding="utf-8"))]

    assert not found, "Unescaped Liquid output in JavaScript:\n" + "\n".join(found)
