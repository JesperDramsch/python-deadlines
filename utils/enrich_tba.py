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
import shutil
import subprocess  # noqa: S404 - subprocess is required for lynx text extraction
import sys
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
    logger = get_logger(__name__)

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
    logger = get_logger(__name__)

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


def prefetch_websites(conferences: list[dict[str, Any]]) -> dict[str, str]:
    """Pre-fetch website content for multiple conferences.

    Parameters
    ----------
    conferences : list[dict[str, Any]]
        List of conference dicts

    Returns
    -------
    dict[str, str]
        Dict mapping conference key (name_year) to website content
    """
    logger = get_logger(__name__)
    content_map: dict[str, str] = {}

    for conf in conferences:
        name = conf.get("conference", "Unknown")
        year = conf.get("year", 0)
        url = conf.get("link", "")
        key = f"{name}_{year}"

        if not url:
            logger.warning(f"No URL for {key}")
            content_map[key] = "No website URL available"
            continue

        logger.info(f"Fetching: {url}")
        content_map[key] = prefetch_website(url)

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
Format: 'YYYY-MM-DD HH:mm:ss' (use 23:59:00 if no time specified)
"""
    else:
        fields_to_extract = [
            "cfp",
            "workshop_deadline",
            "tutorial_deadline",
            "finaid",
            "sponsor",
            "mastodon",
            "bluesky",
        ]
        field_instructions = """
Extract the following fields if found:
- cfp: CFP deadline date (format: 'YYYY-MM-DD HH:mm:ss', use 23:59:00 if no time)
- workshop_deadline: Workshop submission deadline (same format)
- tutorial_deadline: Tutorial submission deadline (same format)
- finaid: Financial aid application URL
- sponsor: Sponsorship information URL
- mastodon: Mastodon profile URL (full URL, e.g., https://fosstodon.org/@pycon)
- bluesky: Bluesky profile URL (full URL, e.g., https://bsky.app/profile/pycon.bsky.social)
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
2. Do NOT guess or approximate dates
3. If a deadline says "TBA", "coming soon", or is not found, set status to "not_announced"
4. If you find partial information, set status to "partial"
5. Assign confidence scores (0.0-1.0) based on how clearly the information is stated
6. For URLs, only include if they appear to be valid absolute URLs

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
    logger = get_logger(__name__)

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
                        return json.loads(content[json_start:json_end])
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
    result = EnrichmentResult()

    if not response:
        return result

    result.summary = response.get("summary", {})

    for conf_data in response.get("conferences", []):
        fields = {}
        for field_name, field_data in conf_data.get("fields", {}).items():
            if isinstance(field_data, dict):
                fields[field_name] = FieldUpdate(
                    value=field_data.get("value", ""),
                    confidence=field_data.get("confidence", 0.0),
                )

        update = ConferenceUpdate(
            conference=conf_data.get("conference", ""),
            year=conf_data.get("year", 0),
            status=conf_data.get("status", "error"),
            confidence=conf_data.get("confidence", 0.0),
            fields=fields,
            notes=conf_data.get("notes", ""),
        )
        result.conferences.append(update)

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
    logger = get_logger(__name__)

    with data_path.open(encoding="utf-8") as f:
        conferences = yaml.safe_load(f) or []

    applied_count = 0
    review_items = []

    for update in updates.conferences:
        if update.status not in ("found", "partial"):
            continue

        # Find matching conference
        matching = None
        for i, conf in enumerate(conferences):
            if conf.get("conference", "").lower() == update.conference.lower() and conf.get("year") == update.year:
                matching = i
                break

        if matching is None:
            logger.warning(f"Conference not found: {update.conference} {update.year}")
            continue

        conf = conferences[matching]
        changes_made = []

        for field_name, field_update in update.fields.items():
            if not field_update.value:
                continue

            if field_update.confidence >= CONFIDENCE_THRESHOLD_AUTO:
                # Auto-apply high confidence updates
                old_value = conf.get(field_name)
                if old_value != field_update.value:
                    conf[field_name] = field_update.value
                    changes_made.append(f"{field_name}: {old_value} -> {field_update.value}")
                    logger.info(
                        f"Applied {field_name} for {update.conference} {update.year} "
                        f"(confidence: {field_update.confidence:.2f})",
                    )
            elif field_update.confidence >= CONFIDENCE_THRESHOLD_REVIEW:
                # Add to review list
                review_items.append(
                    f"{update.conference} {update.year}: "
                    f"{field_name}={field_update.value} "
                    f"(confidence: {field_update.confidence:.2f})",
                )

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

    logger = get_logger(__name__)

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

        # Write review items to GitHub Actions output if available
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with Path(github_output).open("a") as f:
                f.write(f"review_items={json.dumps(review_items)}\n")

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
