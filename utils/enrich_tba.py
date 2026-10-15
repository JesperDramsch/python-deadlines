#!/usr/bin/env python3
"""Enrich TBA conferences with links found on their websites.

A TBA conference is one whose cfp has no date: TBA, TBD, or None for an
edition with no public CfP, whose links are still worth filling. A cancelled
edition is left out.

The enrichment is deterministic. It lists the links on each conference's
homepage with lynx and matches them against known patterns:

- Bluesky profiles (bsky.app/profile/...)
- YouTube channels (youtube.com and youtu.be links)
- Mastodon profiles (/@username patterns)
- Sponsor pages (same-domain URLs with sponsor keywords)
- Financial aid pages (same-domain URLs with finaid or scholarship keywords)

A found link fills a field that is empty or TBA. A link that differs from a
value already set becomes a review item, and the existing value is kept.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # noqa: S404 - subprocess is required for lynx link extraction
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

try:
    from logging_config import get_logger
except ImportError:
    from .logging_config import get_logger


# Constants
TBA_WORDS = ["tba", "tbd", "cancelled", "none", "na", "n/a", "nan", "n.a."]

# Field type categorization for validation
URL_FIELDS = {"sponsor", "finaid", "mastodon", "bluesky", "youtube"}


@dataclass
class ConferenceUpdate:
    """Represents enrichment results for a single conference."""

    conference: str
    year: int
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class EnrichmentResult:
    """Enrichment results for all conferences."""

    conferences: list[ConferenceUpdate] = field(default_factory=list)


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

    # Unknown field type - allow it
    return True, ""


def find_tba_conferences(data_path: Path | None = None) -> list[dict[str, Any]]:
    """Find all conferences with TBA CFP deadlines, leaving out cancelled editions.

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
        # A cancelled edition has nothing to enrich
        if cfp in TBA_WORDS and cfp != "cancelled":
            tba_conferences.append(conf)
            logger.debug(f"Found TBA conference: {conf.get('conference')} {conf.get('year')}")

    logger.info(f"Found {len(tba_conferences)} conferences with TBA CFP")
    return tba_conferences


def get_all_links(url: str) -> list[str]:
    """Get all links from a page using lynx.

    Parameters
    ----------
    url : str
        URL to extract links from

    Returns
    -------
    list[str]
        List of all absolute URLs found on the page
    """
    logger = get_logger()

    lynx_path = shutil.which("lynx")
    if not lynx_path:
        logger.debug("lynx not available for link extraction")
        return []

    try:
        result = subprocess.run(
            [lynx_path, "-dump", "-listonly", "-nonumbers", url],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(f"lynx -listonly failed for {url}: {result.stderr[:100]}")
            return []

        links = []
        for line in result.stdout.strip().split("\n"):
            link = line.strip()
            if link and link.startswith(("http://", "https://")):
                links.append(link)
        return links

    except subprocess.TimeoutExpired:
        logger.debug(f"lynx -listonly timed out for {url}")
        return []
    except Exception as e:
        logger.debug(f"lynx -listonly error for {url}: {e}")
        return []


def _domain_matches(domain: str, hosts: tuple[str, ...]) -> bool:
    """Return True if domain equals one of hosts or is a subdomain of one."""
    return any(domain == h or domain.endswith(f".{h}") for h in hosts)


# A Mastodon profile URL's path is exactly "/@handle" (or "/@user@instance").
# Requiring this shape prevents false positives from other "/@" URLs, e.g.
# Google Maps viewports like "/maps/place/Venue/@52.386807,4.8698442,17z".
MASTODON_PROFILE_RE = re.compile(r"^/@[A-Za-z0-9_][\w.-]*(?:@[\w.-]+)?/?$")

# Known Mastodon instances (common ones in tech/Python community)
MASTODON_INSTANCES = {
    "mastodon.social",
    "mastodon.online",
    "fosstodon.org",
    "hachyderm.io",
    "techhub.social",
    "mstdn.social",
    "infosec.exchange",
    "mas.to",
    "toot.community",
    "social.coop",
    "mathstodon.xyz",
    "scholar.social",
}


def extract_links_from_url(url: str) -> dict[str, str]:
    """Extract known field values from page links deterministically.

    This function finds social media links, sponsor pages and financial aid
    pages by pattern matching.

    Parameters
    ----------
    url : str
        URL to extract links from

    Returns
    -------
    dict[str, str]
        Dict mapping field names to found URLs
    """
    logger = get_logger()
    links = get_all_links(url)

    if not links:
        return {}

    found: dict[str, str] = {}
    seen_types: set[str] = set()  # Track which types we've found

    # Pre-parse the base URL for same-domain checks
    base_domain = urlparse(url).netloc.lower()

    # Sponsor keywords
    sponsor_keywords = ["sponsor", "sponsorship", "partner", "become-a-sponsor", "sponsoring"]

    # Financial aid keywords
    finaid_keywords = [
        "financial-aid",
        "finaid",
        "scholarship",
        "grant",
        "travel-grant",
        "travel-funding",
        "diversity",
        "assistance",
        "opportunity-grant",
        "opportunity-program",
        "aid-program",
        "funding",
    ]

    for link in links:
        link_lower = link.lower()
        parsed_link = urlparse(link)
        link_domain = parsed_link.netloc.lower()

        is_youtube = _domain_matches(link_domain, ("youtube.com", "youtu.be"))
        is_twitter = _domain_matches(link_domain, ("twitter.com", "x.com"))

        # Bluesky - always bsky.app/profile/
        if "bluesky" not in seen_types and "bsky.app/profile/" in link_lower:
            found["bluesky"] = link
            seen_types.add("bluesky")
            logger.debug(f"  Found bluesky: {link}")

        # YouTube - youtube.com/@channel or youtu.be links
        elif "youtube" not in seen_types and is_youtube:
            found["youtube"] = link
            seen_types.add("youtube")
            logger.debug(f"  Found youtube: {link}")

        # Mastodon - /@username pattern on known instances or any instance
        # Exclude Twitter/X and YouTube which also use /@username patterns
        elif "mastodon" not in seen_types and "/@" in link:
            # Skip Twitter/X and YouTube domains
            if is_twitter or is_youtube:
                pass
            elif link_domain in MASTODON_INSTANCES or "mastodon" in link_domain or "toot" in link_domain:
                found["mastodon"] = link
                seen_types.add("mastodon")
                logger.debug(f"  Found mastodon: {link}")
            elif MASTODON_PROFILE_RE.match(parsed_link.path):
                # Path is exactly /@username - likely Mastodon-compatible
                found["mastodon"] = link
                seen_types.add("mastodon")
                logger.debug(f"  Found mastodon (generic): {link}")

        # Sponsor page (must be same domain)
        if (
            "sponsor" not in seen_types
            and any(kw in link_lower for kw in sponsor_keywords)
            and parsed_link.netloc.lower() == base_domain
        ):
            found["sponsor"] = link
            seen_types.add("sponsor")
            logger.debug(f"  Found sponsor: {link}")

        # Financial aid page (must be same domain)
        if (
            "finaid" not in seen_types
            and any(kw in link_lower for kw in finaid_keywords)
            and parsed_link.netloc.lower() == base_domain
        ):
            found["finaid"] = link
            seen_types.add("finaid")
            logger.debug(f"  Found finaid: {link}")

    return found


def run_deterministic_extraction(conferences: list[dict[str, Any]]) -> EnrichmentResult:
    """Run deterministic link extraction on all conferences.

    This extracts social media links and sponsor and financial aid pages by
    pattern matching.

    Parameters
    ----------
    conferences : list[dict[str, Any]]
        List of conference dicts

    Returns
    -------
    EnrichmentResult
        Result with the fields found for each conference
    """
    logger = get_logger()
    result = EnrichmentResult()

    for conf in conferences:
        name = conf.get("conference", "Unknown")
        year = conf.get("year", 0)
        url = conf.get("link", "")

        if not url:
            continue

        logger.debug(f"Deterministic extraction for {name} {year}")
        extracted = extract_links_from_url(url)

        if extracted:
            update = ConferenceUpdate(
                conference=name,
                year=year,
                fields=extracted,
            )
            result.conferences.append(update)
            logger.info(f"  {name} {year}: found {list(extracted.keys())}")

    return result


def apply_updates(
    data_path: Path,
    updates: EnrichmentResult,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """Apply found links to empty or TBA fields in conferences.yml.

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
        # Find matching conference
        matching = None
        for i, conf in enumerate(conferences):
            if conf.get("conference") == update.conference and conf.get("year") == update.year:
                matching = i
                break

        if matching is None:
            logger.warning(f"Conference not found: {update.conference} {update.year}")
            continue

        conf = conferences[matching]
        changes_made = []

        logger.debug(f"Processing updates for: {update.conference} {update.year}")

        for field_name, value in update.fields.items():
            if not value:
                logger.debug(f"  Skipping {field_name}: empty value")
                continue

            # Validate field value before applying
            is_valid, validation_reason = validate_field_value(field_name, value)
            if not is_valid:
                logger.warning(
                    f"  REJECTED {field_name} for {update.conference} {update.year}: "
                    f"validation failed - {validation_reason}",
                )
                continue

            # Apply only if the field is empty or TBA
            old_value = conf.get(field_name)
            old_value_str = str(old_value).lower().strip() if old_value else ""

            # Skip if field already has a valid (non-TBA) value
            if old_value and old_value_str not in TBA_WORDS and old_value_str != "":
                # Add to review if the values differ - might be worth checking
                if old_value != value:
                    review_items.append(
                        f"⚠️ {update.conference} {update.year}: {field_name} - "
                        f"existing='{old_value}' vs found='{value}' (kept existing)",
                    )
                    logger.info(
                        f"  REVIEW {field_name} for {update.conference} {update.year}: "
                        f"kept '{old_value}', found '{value}'",
                    )
                else:
                    logger.debug(
                        f"  Skipping {field_name}: already has matching value '{old_value}'",
                    )
                continue

            conf[field_name] = value
            changes_made.append(f"{field_name}: {old_value} -> {value}")
            logger.info(
                f"APPLIED {field_name} for {update.conference} {update.year}: '{old_value}' -> '{value}'",
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
    dry_run: bool = False,
    data_path: Path | None = None,
) -> bool:
    """Main function to enrich TBA conferences.

    Finds the conferences with a TBA CFP, extracts social links and sponsor
    and financial aid pages from their websites, and fills the fields that
    are empty or TBA.

    Parameters
    ----------
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

    if data_path is None:
        data_path = Path("_data/conferences.yml")

    # Step 1: Find TBA conferences
    logger.info("Finding TBA conferences...")
    tba_conferences = find_tba_conferences(data_path)

    if not tba_conferences:
        logger.info("No TBA conferences found")
        return True

    # Step 2: Extract links from the conference websites
    logger.info("Running deterministic link extraction...")
    result = run_deterministic_extraction(tba_conferences)
    det_count = len([c for c in result.conferences if c.fields])
    logger.info(f"Deterministic: found links for {det_count} conferences")

    # Step 3: Apply updates
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
        review_md += "The following links differ from values already set. The existing values were kept:\n\n"
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
    parser = argparse.ArgumentParser(description="Enrich TBA conferences with links from their websites")
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
        dry_run=args.dry_run,
        data_path=args.data_path,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
