#!/usr/bin/env python3
"""Enrich TBA conferences by crawling websites and extracting CFP data using Claude API.

This module provides functions to:
1. Find conferences with TBA CFP deadlines
2. Pre-fetch conference websites
3. Call Claude API to extract CFP information
4. Apply high-confidence updates to conferences.yml
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # noqa: S404 - subprocess is required for lynx text extraction
import sys
import zoneinfo
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

try:
    from logging_config import get_logger
except ImportError:
    from .logging_config import get_logger


# Constants
TBA_WORDS = ["tba", "tbd", "cancelled", "none", "na", "n/a", "nan", "n.a."]
CONFIDENCE_THRESHOLD_AUTO = 0.8
CONFIDENCE_THRESHOLD_REVIEW = 0.5
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MAX_CONTENT_LENGTH = 15000  # Max characters per conference website

# Field type categorization for validation
URL_FIELDS = {"sponsor", "finaid", "mastodon", "bluesky", "cfp_link"}
DATE_FIELDS = {"cfp", "workshop_deadline", "tutorial_deadline"}
TIMEZONE_FIELD = "timezone"


@dataclass
class FieldUpdate:
    """Represents a single field update with confidence."""

    value: str
    confidence: float


@dataclass
class ConferenceUpdate:
    """Represents enrichment results for a single conference."""

    conference: str
    year: int
    status: str  # found | partial | not_announced | error
    confidence: float
    fields: dict[str, FieldUpdate] = field(default_factory=dict)
    notes: str = ""


@dataclass
class EnrichmentResult:
    """Complete enrichment result from Claude API."""

    conferences: list[ConferenceUpdate] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def validate_field_value(field_name: str, value: str) -> tuple[bool, str]:
    """Validate that a field value matches expected format.

    Parameters
    ----------
    field_name : str
        Name of the field being validated
    value : str
        Value to validate

    Returns
    -------
    tuple[bool, str]
        (is_valid, reason) - True if valid, False with reason if not
    """
    if not value or not value.strip():
        return False, "Empty value"

    value = value.strip()

    if field_name in URL_FIELDS:
        if not value.startswith(("https://", "http://")):
            return False, f"URL must start with https:// or http://, got: {value[:50]}"
        return True, ""

    if field_name in DATE_FIELDS:
        if not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", value):
            return False, f"Date must be YYYY-MM-DD HH:mm:ss format, got: {value}"
        return True, ""

    if field_name == TIMEZONE_FIELD:
        # Must be valid IANA timezone with slash (reject abbreviations)
        if "/" not in value:
            return False, f"Timezone must be IANA format with slash (e.g., America/Chicago), got: {value}"
        try:
            zoneinfo.ZoneInfo(value)
            return True, ""
        except zoneinfo.ZoneInfoNotFoundError:
            return False, f"Invalid IANA timezone: {value}"

    # Unknown field type - allow it
    return True, ""


def find_tba_conferences(data_path: Path | None = None) -> list[dict[str, Any]]:
    """Find all conferences with TBA CFP deadlines.

    Parameters
    ----------
    data_path : Path | None
        Path to conferences.yml (defaults to _data/conferences.yml)

    Returns
    -------
    list[dict[str, Any]]
        List of conference dicts with TBA CFP deadlines
    """
    logger = get_logger()

    if data_path is None:
        data_path = Path("_data/conferences.yml")

    if not data_path.exists():
        logger.error(f"Conference file not found: {data_path}")
        return []

    with data_path.open(encoding="utf-8") as f:
        conferences = yaml.safe_load(f) or []

    tba_conferences = []
    for conf in conferences:
        cfp = str(conf.get("cfp", "")).lower().strip()
        if cfp in TBA_WORDS:
            tba_conferences.append(conf)
            logger.debug(f"Found TBA conference: {conf.get('conference')} {conf.get('year')}")

    logger.info(f"Found {len(tba_conferences)} conferences with TBA CFP")
    return tba_conferences


def prefetch_website(url: str, timeout: int = 30) -> str:
    """Fetch website content as clean text.

    Parameters
    ----------
    url : str
        Conference website URL
    timeout : int
        Request timeout in seconds

    Returns
    -------
    str
        Cleaned text content from the website
    """
    logger = get_logger()

    # Validate URL before processing
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        logger.warning(f"Invalid URL scheme or missing host: {url}")
        return f"Invalid URL: {url}"

    # Try using lynx for clean text extraction (if available)
    lynx_path = shutil.which("lynx")
    if lynx_path:
        try:
            result = subprocess.run(
                [lynx_path, "-dump", "-nolist", "-nonumbers", "-width=200", url],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout[:MAX_CONTENT_LENGTH]
        except subprocess.TimeoutExpired:
            pass

    # Fallback to requests + basic HTML stripping
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "python-deadlines-bot/1.0"})
        response.raise_for_status()

        # Basic HTML to text conversion
        import re

        text = response.text
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:MAX_CONTENT_LENGTH]
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return f"Error fetching website: {e}"


def find_cfp_links(html: str, base_url: str) -> list[str]:
    """Find CFP-related links in HTML content.

    Parameters
    ----------
    html : str
        Raw HTML content
    base_url : str
        Base URL for resolving relative links

    Returns
    -------
    list[str]
        List of absolute URLs to CFP-related pages
    """
    from urllib.parse import urljoin

    # Keywords that suggest a CFP/speaker page (multilingual)
    cfp_keywords = [
        # English - core
        "cfp",
        "call-for",
        "callfor",
        "call_for",
        "speaker",
        "proposal",
        "submit",
        "submission",
        "contribute",
        "talk",
        "present",
        # English - academic/extended
        "abstract",
        "paper",
        "papers",
        "apply",
        "application",
        "participate",
        "deadline",
        "deadlines",
        "important-dates",
        "dates",
        "lightning",
        "poster",
        "tutorial",
        "workshop",
        "session",
        # Spanish (convocatoria=call, ponente=speaker, propuesta=proposal, enviar=submit,
        #          fechas=dates, participar=participate)
        "convocatoria",
        "ponente",
        "propuesta",
        "enviar",
        "fechas",
        "participar",
        # German (einreichung=submission, vortrag=talk, sprecher=speaker, beitrag=contribution,
        #         aufruf=call, teilnehmen=participate, termine=dates, wichtige-termine=important-dates)
        "einreichung",
        "vortrag",
        "sprecher",
        "beitrag",
        "aufruf",
        "teilnehmen",
        "termine",
        "wichtige-termine",
        # Portuguese (chamada=call, palestrante=speaker, proposta=proposal,
        #             submissão=submission, participar=participate, datas=dates)
        "chamada",
        "palestrante",
        "proposta",
        "submissao",
        "submissão",
        "participar",
        "datas",
        # French (appel=call, orateur=speaker, soumission=submission, conférencier=lecturer,
        #         participer=participate, dates-importantes=important-dates)
        "appel",
        "orateur",
        "soumission",
        "conferencier",
        "conférencier",
        "participer",
        "dates-importantes",
        # Japanese romanized (happyo=発表=presentation, oubo=応募=application,
        #                     teishutsu=提出=submission, kouen=講演=lecture, boshu=募集=recruitment)
        "happyo",
        "oubo",
        "teishutsu",
        "kouen",
        "boshu",
        # Chinese romanized (zhenggao=征稿=call-for-papers, yanjiang=演讲=speech,
        #                    tijiao=提交=submit, tougao=投稿=contribute)
        "zhenggao",
        "yanjiang",
        "tijiao",
        "tougao",
        # Dutch (inzending=submission, spreker=speaker, voorstel=proposal, deelnemen=participate)
        "inzending",
        "spreker",
        "voorstel",
        "deelnemen",
        # Italian (proposta=proposal, relatore=speaker, invio=submission, partecipare=participate)
        "proposta",
        "relatore",
        "invio",
        "partecipare",
        # Polish (zgłoszenie=submission, prelegent=speaker, referat=paper, wystąpienie=presentation)
        "zgloszenie",
        "prelegent",
        "referat",
        "wystapienie",
        # Russian romanized (doklad=доклад=report/talk, zayavka=заявка=application,
        #                    vystuplenie=выступление=presentation, uchastie=участие=participation)
        "doklad",
        "zayavka",
        "vystuplenie",
        "uchastie",
    ]

    # Find all href links
    link_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    links = link_pattern.findall(html)

    cfp_links = []
    seen = set()

    for link in links:
        link_lower = link.lower()

        # Check if link contains CFP-related keywords
        if any(kw in link_lower for kw in cfp_keywords):
            # Resolve relative URLs
            absolute_url = urljoin(base_url, link)

            # Skip fragments, mailto, javascript, etc.
            if absolute_url.startswith(("http://", "https://")) and absolute_url not in seen:
                seen.add(absolute_url)
                cfp_links.append(absolute_url)

    return cfp_links[:3]  # Limit to 3 CFP pages max


def prefetch_websites(conferences: list[dict[str, Any]]) -> dict[str, str]:
    """Pre-fetch website content for multiple conferences.

    Also fetches CFP-related subpages if found on the main page.

    Parameters
    ----------
    conferences : list[dict[str, Any]]
        List of conference dicts

    Returns
    -------
    dict[str, str]
        Dict mapping conference key (name_year) to website content
    """
    logger = get_logger()
    content_map: dict[str, str] = {}

    for conf in conferences:
        name = conf.get("conference", "Unknown")
        year = conf.get("year", 0)
        url = conf.get("link", "")
        cfp_link = conf.get("cfp_link", "")  # Use explicit cfp_link if available
        key = f"{name}_{year}"

        if not url:
            logger.warning(f"No URL for {key}")
            content_map[key] = "No website URL available"
            continue

        logger.info(f"Fetching: {url}")

        # First, get raw HTML to find CFP links
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "python-deadlines-bot/1.0"},
            )
            response.raise_for_status()
            raw_html = response.text
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch HTML from {url}: {e}")
            raw_html = ""

        # Get main page content
        main_content = prefetch_website(url)

        # Find and fetch CFP-related subpages
        additional_content = []

        # If cfp_link is explicitly set, prioritize it
        cfp_links_to_fetch = []
        if cfp_link:
            cfp_links_to_fetch.append(cfp_link)

        # Also look for CFP links in the HTML
        if raw_html:
            found_links = find_cfp_links(raw_html, url)
            for link in found_links:
                if link not in cfp_links_to_fetch and link != url:
                    cfp_links_to_fetch.append(link)

        # Fetch CFP subpages (limit to 2 to avoid too much content)
        for cfp_url in cfp_links_to_fetch[:2]:
            logger.debug(f"  Also fetching CFP page: {cfp_url}")
            cfp_content = prefetch_website(cfp_url)
            if cfp_content and not cfp_content.startswith("Error"):
                additional_content.append(f"\n\n--- CFP Page ({cfp_url}) ---\n{cfp_content}")

        # Combine all content
        combined = main_content + "".join(additional_content)
        content_map[key] = combined[:MAX_CONTENT_LENGTH]

    return content_map


def build_enrichment_prompt(
    conferences: list[dict[str, Any]],
    content_map: dict[str, str],
    enrichment_level: str = "full",
) -> str:
    """Build the Claude API prompt for batch enrichment.

    Parameters
    ----------
    conferences : list[dict[str, Any]]
        List of conference dicts with TBA CFP
    content_map : dict[str, str]
        Dict mapping conference key to website content
    enrichment_level : str
        Enrichment level: 'quick' (CFP only) or 'full' (all fields)

    Returns
    -------
    str
        Formatted prompt string for Claude API
    """
    if enrichment_level == "quick":
        fields_to_extract = ["cfp"]
        field_instructions = """
Extract ONLY the CFP (Call for Proposals) deadline date.
Convert to format: 'YYYY-MM-DD HH:mm:ss' (use 23:59:00 if no time specified)

Date formats you may encounter:
- "February 8, 2026" → "2026-02-08 23:59:00"
- "8th of February 2026 at 23:59 CET" → "2026-02-08 23:59:00"
- "2026-02-08" → "2026-02-08 23:59:00"
"""
    else:
        fields_to_extract = [
            "cfp",
            "workshop_deadline",
            "tutorial_deadline",
            "timezone",
            "finaid",
            "sponsor",
            "mastodon",
            "bluesky",
        ]
        field_instructions = """
Extract the following fields if found:
- cfp: CFP deadline date (MUST be format 'YYYY-MM-DD HH:mm:ss', use 23:59:00 if no time)
- workshop_deadline: Workshop submission deadline (MUST be format 'YYYY-MM-DD HH:mm:ss')
- tutorial_deadline: Tutorial submission deadline (MUST be format 'YYYY-MM-DD HH:mm:ss')
- timezone: Conference timezone (MUST be IANA format with slash, e.g., 'America/Chicago', 'Europe/Berlin')
  - NEVER use abbreviations like EST, CEST, PST, UTC - ONLY full IANA names with slash
- finaid: Financial aid application URL (MUST start with https://)
- sponsor: Sponsorship information URL (MUST start with https://)
- mastodon: Mastodon profile URL (MUST be full https:// URL like https://fosstodon.org/@pycon)
- bluesky: Bluesky profile URL (MUST be full https:// URL like https://bsky.app/profile/pycon.bsky.social)

CRITICAL RULES FOR VALUES:
- URL fields (finaid, sponsor, mastodon, bluesky): ONLY include if you find an actual URL starting with https://
  - If you only find descriptive text like "Sponsorship available", DO NOT include it
  - The value MUST be a valid URL, not a description
- Date fields (cfp, workshop_deadline, tutorial_deadline): MUST be exactly 'YYYY-MM-DD HH:mm:ss' format
- Timezone: MUST be IANA format with slash (America/New_York), NEVER abbreviations (EST, CEST)
- Leave field EMPTY (do not include it) if you only find descriptive text, not the actual value

Date conversion examples:
- "February 8, 2026" → "2026-02-08 23:59:00"
- "8th of February 2026 at 23:59 CET" → "2026-02-08 23:59:00"
- "Feb 8" (current year context) → "2026-02-08 23:59:00"
"""

    conference_sections = []
    for conf in conferences:
        name = conf.get("conference", "Unknown")
        year = conf.get("year", 0)
        url = conf.get("link", "")
        key = f"{name}_{year}"
        content = content_map.get(key, "No content available")

        conference_sections.append(
            f"""
### {name} {year}
URL: {url}

Website Content:
```
{content[:8000]}
```
""",
        )

    prompt = f"""You are an expert at extracting conference information from websites.
Analyze the following Python conference websites and extract CFP (Call for Proposals) information.

{field_instructions}

IMPORTANT RULES:
1. Only extract dates that are EXPLICITLY stated on the website
2. Do NOT guess or approximate dates - if unsure, set status to "not_announced"
3. If a deadline says "TBA", "coming soon", or is not found, set status to "not_announced"
4. Use status "found" when you have extracted all requested date fields with clear values
5. Use status "partial" ONLY when some fields are found but others are missing
6. CONFIDENCE SCORING:
   - 0.9-1.0: Date is clearly and unambiguously stated (even if in human-readable format)
   - 0.7-0.9: Date is stated but requires interpretation (e.g., relative dates)
   - 0.5-0.7: Date is implied or uncertain
   - Below 0.5: Do not include - set status to "not_announced" instead
7. For URLs, only include if they appear to be valid absolute URLs

Fields to extract: {', '.join(fields_to_extract)}

CONFERENCES TO ANALYZE:
{''.join(conference_sections)}

Respond with ONLY valid JSON in this exact format:
{{
  "conferences": [
    {{
      "conference": "Conference Name",
      "year": 2026,
      "status": "found | partial | not_announced | error",
      "confidence": 0.0-1.0,
      "fields": {{
        "cfp": {{ "value": "2026-02-15 23:59:00", "confidence": 0.95 }},
        ... other fields as applicable
      }},
      "notes": "Optional notes about what was found"
    }}
  ],
  "summary": {{
    "total": 5,
    "found": 3,
    "partial": 1,
    "not_announced": 1,
    "errors": 0
  }}
}}
"""
    return prompt


def call_claude_api(
    prompt: str,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 4096,
) -> dict[str, Any] | None:
    """Call Claude API with the enrichment prompt.

    Parameters
    ----------
    prompt : str
        The formatted prompt
    api_key : str
        Anthropic API key
    model : str
        Model to use
    max_tokens : int
        Maximum tokens in response

    Returns
    -------
    dict[str, Any] | None
        Parsed JSON response or None on error
    """
    logger = get_logger()

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(3):
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("content", [{}])[0].get("text", "")

                # Debug: Log the raw API response
                logger.debug("=" * 80)
                logger.debug("RAW CLAUDE API RESPONSE:")
                logger.debug("=" * 80)
                logger.debug(content)
                logger.debug("=" * 80)

                # Log token usage
                usage = result.get("usage", {})
                logger.info(
                    f"API usage - Input: {usage.get('input_tokens', 0)}, Output: {usage.get('output_tokens', 0)}",
                )

                # Parse JSON from response
                try:
                    # Try to find JSON in the response
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        parsed_json = json.loads(content[json_start:json_end])
                        logger.debug("Successfully parsed JSON from response")
                        return parsed_json
                    logger.error("No valid JSON found in response")
                    return None
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return None

            if response.status_code in (429, 529):
                logger.warning(f"Rate limited (HTTP {response.status_code}), attempt {attempt + 1}/3")
                import time

                time.sleep((attempt + 1) * 5)
                continue

            logger.error(f"API error: HTTP {response.status_code} - {response.text}")
            return None

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    return None


def parse_response(response: dict[str, Any]) -> EnrichmentResult:
    """Parse Claude API response into structured result.

    Parameters
    ----------
    response : dict[str, Any]
        Raw JSON response from Claude API

    Returns
    -------
    EnrichmentResult
        EnrichmentResult with parsed updates
    """
    logger = get_logger()
    result = EnrichmentResult()

    if not response:
        logger.debug("Empty response received")
        return result

    result.summary = response.get("summary", {})
    logger.debug(f"Response summary: {result.summary}")

    for conf_data in response.get("conferences", []):
        conf_name = conf_data.get("conference", "")
        conf_year = conf_data.get("year", 0)
        conf_status = conf_data.get("status", "error")

        logger.debug(f"Parsing conference: {conf_name} {conf_year} (status: {conf_status})")

        fields = {}
        for field_name, field_data in conf_data.get("fields", {}).items():
            if isinstance(field_data, dict):
                field_value = field_data.get("value", "")
                field_confidence = field_data.get("confidence", 0.0)
                fields[field_name] = FieldUpdate(
                    value=field_value,
                    confidence=field_confidence,
                )
                logger.debug(
                    f"  Parsed field: {field_name} = '{field_value}' (confidence: {field_confidence:.2f})",
                )

        update = ConferenceUpdate(
            conference=conf_name,
            year=conf_year,
            status=conf_status,
            confidence=conf_data.get("confidence", 0.0),
            fields=fields,
            notes=conf_data.get("notes", ""),
        )
        result.conferences.append(update)

    logger.debug(f"Parsed {len(result.conferences)} conferences from response")
    return result


def apply_updates(
    data_path: Path,
    updates: EnrichmentResult,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """Apply high-confidence updates to conferences.yml.

    Parameters
    ----------
    data_path : Path
        Path to conferences.yml
    updates : EnrichmentResult
        EnrichmentResult with updates to apply
    dry_run : bool
        If True, don't write changes

    Returns
    -------
    tuple[int, list[str]]
        Tuple of (count of updates applied, list of review items)
    """
    logger = get_logger()

    with data_path.open(encoding="utf-8") as f:
        conferences = yaml.safe_load(f) or []

    applied_count = 0
    review_items = []

    for update in updates.conferences:
        if update.status not in ("found", "partial"):
            continue

        # Find matching conference (strip year suffix if Claude included it)
        matching = None
        update_name = update.conference.lower().replace(str(update.year), "").strip()
        for i, conf in enumerate(conferences):
            conf_name = conf.get("conference", "").lower()
            if (conf_name == update_name or conf_name == update.conference.lower()) and conf.get("year") == update.year:
                matching = i
                break

        if matching is None:
            logger.warning(f"Conference not found: {update.conference} {update.year}")
            continue

        conf = conferences[matching]
        changes_made = []

        logger.debug(f"Processing updates for: {update.conference} {update.year}")

        for field_name, field_update in update.fields.items():
            if not field_update.value:
                logger.debug(f"  Skipping {field_name}: empty value")
                continue

            # Validate field value before applying
            is_valid, validation_reason = validate_field_value(field_name, field_update.value)
            if not is_valid:
                logger.warning(
                    f"  REJECTED {field_name} for {update.conference} {update.year}: "
                    f"validation failed - {validation_reason}",
                )
                continue

            logger.debug(
                f"  Field {field_name}: value='{field_update.value}', "
                f"confidence={field_update.confidence:.2f}, valid={is_valid}",
            )

            if field_update.confidence >= CONFIDENCE_THRESHOLD_AUTO:
                # Auto-apply high confidence updates - but ONLY if field is empty/TBA
                old_value = conf.get(field_name)
                old_value_str = str(old_value).lower().strip() if old_value else ""

                # Skip if field already has a valid (non-TBA) value
                if old_value and old_value_str not in TBA_WORDS and old_value_str != "":
                    # Add to review if the values differ - might be worth checking
                    if old_value != field_update.value:
                        review_items.append(
                            f"⚠️ {update.conference} {update.year}: {field_name} - "
                            f"existing='{old_value}' vs found='{field_update.value}' "
                            f"(kept existing, confidence: {field_update.confidence:.2f})",
                        )
                        logger.info(
                            f"  REVIEW {field_name} for {update.conference} {update.year}: "
                            f"kept '{old_value}', found '{field_update.value}'",
                        )
                    else:
                        logger.debug(
                            f"  Skipping {field_name}: already has matching value '{old_value}'",
                        )
                    continue

                if old_value != field_update.value:
                    conf[field_name] = field_update.value
                    changes_made.append(f"{field_name}: {old_value} -> {field_update.value}")
                    logger.info(
                        f"APPLIED {field_name} for {update.conference} {update.year}: "
                        f"'{old_value}' -> '{field_update.value}' "
                        f"(confidence: {field_update.confidence:.2f})",
                    )
                else:
                    logger.debug(f"  Skipping {field_name}: value unchanged")
            elif field_update.confidence >= CONFIDENCE_THRESHOLD_REVIEW:
                # Add to review list
                logger.debug(f"  Adding {field_name} to review list (confidence below auto threshold)")
                review_items.append(
                    f"{update.conference} {update.year}: "
                    f"{field_name}={field_update.value} "
                    f"(confidence: {field_update.confidence:.2f})",
                )
            else:
                logger.debug(f"  Skipping {field_name}: confidence {field_update.confidence:.2f} too low")

        if changes_made:
            conferences[matching] = conf
            applied_count += 1

    if not dry_run and applied_count > 0:
        # Write back to file
        from tidy_conf import write_conference_yaml

        write_conference_yaml(conferences, data_path)
        logger.info(f"Written {applied_count} updates to {data_path}")

    return applied_count, review_items


def enrich_tba_conferences(
    enrichment_level: str = "full",
    api_key: str | None = None,
    dry_run: bool = False,
    data_path: Path | None = None,
) -> bool:
    """Main function to enrich TBA conferences.

    Parameters
    ----------
    enrichment_level : str
        Enrichment level: 'quick' (CFP only) or 'full' (all fields)
    api_key : str | None
        Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
    dry_run : bool
        If True, don't write changes
    data_path : Path | None
        Path to conferences.yml

    Returns
    -------
    bool
        True if successful, False otherwise
    """
    import os

    logger = get_logger()

    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set")
            return False

    if data_path is None:
        data_path = Path("_data/conferences.yml")

    # Step 1: Find TBA conferences
    logger.info("Finding TBA conferences...")
    tba_conferences = find_tba_conferences(data_path)

    if not tba_conferences:
        logger.info("No TBA conferences found")
        return True

    # Step 2: Pre-fetch websites
    logger.info("Pre-fetching conference websites...")
    content_map = prefetch_websites(tba_conferences)

    # Step 3: Build and send prompt
    logger.info(f"Calling Claude API with {enrichment_level} enrichment...")
    prompt = build_enrichment_prompt(tba_conferences, content_map, enrichment_level)

    # Debug: Log the full prompt for debugging
    logger.debug("=" * 80)
    logger.debug("FULL PROMPT SENT TO CLAUDE API:")
    logger.debug("=" * 80)
    logger.debug(prompt)
    logger.debug("=" * 80)

    response = call_claude_api(prompt, api_key)

    if not response:
        logger.error("Failed to get response from Claude API")
        return False

    # Step 4: Parse response
    logger.info("Parsing response...")
    result = parse_response(response)

    logger.info(
        f"Results: {result.summary.get('found', 0)} found, "
        f"{result.summary.get('partial', 0)} partial, "
        f"{result.summary.get('not_announced', 0)} not announced",
    )

    # Step 5: Apply updates
    if dry_run:
        logger.info("Dry run - not applying changes")

    applied, review_items = apply_updates(data_path, result, dry_run)

    if applied > 0:
        logger.info(f"Applied {applied} updates")

    if review_items:
        logger.info("Items for manual review:")
        for item in review_items:
            logger.info(f"  - {item}")

        # Build markdown content for PR description
        review_md = "## 👀 Items for Manual Review\n\n"
        review_md += "The following items had moderate confidence and need verification:\n\n"
        for item in review_items:
            review_md += f"- [ ] {item}\n"
        review_md += "\nPlease verify these values before merging.\n"

        # Write to a file that can be included in PR descriptions
        review_file = Path(".github/enrichment_review.md")
        review_file.parent.mkdir(parents=True, exist_ok=True)
        review_file.write_text(review_md, encoding="utf-8")
        logger.info(f"Review items written to {review_file}")

        # Write review items to GitHub Actions output if available
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with Path(github_output).open("a") as f:
                f.write(f"review_items={json.dumps(review_items)}\n")
                # Also output as multiline for PR body
                f.write("review_markdown<<EOF\n")
                f.write(review_md)
                f.write("EOF\n")

        # Write to GitHub step summary if available
        github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if github_summary:
            with Path(github_summary).open("a") as f:
                f.write(review_md)

    return True


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Enrich TBA conferences with CFP data")
    parser.add_argument(
        "--level",
        choices=["quick", "full"],
        default="full",
        help="Enrichment level: quick (CFP only) or full (all fields)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write changes, just show what would be updated",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help="Path to conferences.yml (default: _data/conferences.yml)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    args = parser.parse_args()

    # Set up logging
    from logging_config import setup_logging

    setup_logging(level=args.log_level)

    success = enrich_tba_conferences(
        enrichment_level=args.level,
        dry_run=args.dry_run,
        data_path=args.data_path,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
