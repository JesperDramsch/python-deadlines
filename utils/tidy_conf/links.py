import re
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm


def get_cache_location():
    # Check if the URL is cached
    cache_file = Path("utils", "tidy_conf", "data", ".tmp", "no_archive.txt")
    cache_file_archived = Path("utils", "tidy_conf", "data", ".tmp", "archived_links.txt")
    return cache_file, cache_file_archived


def get_cache():
    cache_file, cache_file_archived = get_cache_location()

    # Create the cache file if it doesn't exist
    cache_file.touch()
    cache_file_archived.touch()

    # Read the cache file
    cache = set(cache_file.read_text(encoding="utf-8").split("\n")[:-1])
    cache_archived = set(cache_file_archived.read_text(encoding="utf-8").split("\n")[:-1])

    return cache, cache_archived


def check_link_availability(url, start, cache=None, cache_archived=None):
    """Checks if a URL is available.

    If not, tries to retrieve an archived version from the Wayback Machine.
    Can't use caching because we have different years for the same url.

    Automatically redirects to the final URL if it was redirected within the same domain.

    Automatically caches old (5+ years) URLs.

    Note: Some URLs may not be available or archived. These return None and are logged.
    """
    # If it's archived already, return the URL
    if url.startswith(("https://web.archive.org", "http://web.archive.org")):
        return url

    # Get the cache
    if cache is None or cache_archived is None:
        cache, cache_archived = get_cache()

    cache_file, _ = get_cache_location()

    # Check if the URL is in the cache
    if url in cache and url not in cache_archived:
        tqdm.write(f"URL {url} is cached as not found. Returning original URL.")
        return url

    # If the URL is younger than 5 years, check if it's available
    if start > datetime.now(tz=timezone.utc).date() - timedelta(days=5 * 365):
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            final_url = response.url
            # Check if the final URL is within the same domain as the original URL
            if urlparse(url).netloc == urlparse(final_url).netloc and final_url != url:
                # Don't cache the redirect if it suddenly has a query string
                tqdm.write(f"URL {url} was redirected within the same domain to: {final_url}")
                if "?" in final_url and "?" not in url:
                    tqdm.write("Warning: The final URL contains a query string, but the original URL does not.")
                    # Return original URL to avoid using redirected URL with query string
                    return url
                return final_url  # Use the final URL for the rest of the process
            if response.status_code != 200:
                tqdm.write(
                    (
                        f"Link {url} is not available (status code: {response.status_code})."
                        "Trying to find an archived version..."
                    ),
                )
            else:
                if start > datetime.now(tz=timezone.utc).date():
                    attempt_archive_url(url, cache_archived)
                return url
        except requests.RequestException as e:
            tqdm.write(f"An error occurred: {e}. Trying to find an archived version...")

    # Try to get an archived version from the Wayback Machine or return original URL
    archive_url = f"https://archive.org/wayback/available?url={url}&timestamp={start.strftime('%Y%m%d%H%M%S')}"
    try:
        archive_response = requests.get(archive_url, timeout=10)
        # Make sure the status code is valid (200)
        if archive_response.status_code == 200:
            data = archive_response.json()
            # Get the "closest available" snapshot URL to a date
            if (
                "archived_snapshots" in data
                and data["archived_snapshots"]
                and "closest" in data["archived_snapshots"]
                and data["archived_snapshots"]["closest"]
                and data["archived_snapshots"]["closest"].get("available", False)
            ):
                archived_url = data["archived_snapshots"]["closest"]["url"].replace(":80/", "/")
                if archived_url[4] == ":":
                    archived_url = archived_url[:4] + "s" + archived_url[4:]
                tqdm.write(f"Found archived version: {archived_url}")
                return archived_url
            tqdm.write("No archived version found.")
            attempt_archive_url(url, cache_archived)
            with cache_file.open("a") as f:
                f.write(url + "\n")
            return url

        tqdm.write("Failed to retrieve archived version.")
        return url
    except requests.RequestException as e:
        tqdm.write(f"An error occurred while retrieving the archived version: {e}")
        return url


def attempt_archive_url(url, cache=None):
    """Attempts to archive a URL using the Wayback Machine."""
    # Read the cache file
    if cache is None:
        _, cache = get_cache()

    # Check if the URL is in the cache
    if url in cache:
        tqdm.write(f"URL {url} was already archived.")
        return

    try:
        tqdm.write(f"Attempting archive of {url}.")
        headers = {"User-Agent": "Pythondeadlin.es Archival Attempt/0.1 (https://pythondeadlin.es)"}
        archive_response = requests.get("https://web.archive.org/save/" + url, timeout=30, headers=headers)
        if archive_response.status_code == 200:
            _, cache_file = get_cache_location()
            with cache_file.open("a") as f:
                f.write(url + "\n")
            tqdm.write(f"Successfully archived {url}.")
    except requests.RequestException as e:
        tqdm.write(f"An error occurred while attempting to archive: {e}")


def parse_mastodon_url(url: str) -> tuple[str, str] | None:
    """Parse a Mastodon URL into (instance, username).

    Args:
        url: Full Mastodon profile URL (e.g., https://fosstodon.org/@pycon)

    Returns
    -------
    tuple[str, str] | None
        Tuple of (instance, username) or None if URL format is invalid.
    """
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        # Match /@username or @username patterns
        match = re.match(r"^/?@(\w+)$", parsed.path)
        if match:
            return (parsed.netloc, match.group(1))
        return None
    except Exception:
        return None


def check_mastodon_migration(mastodon_url: str, max_depth: int = 5) -> str | None:
    """Check if a Mastodon account has migrated and return the new URL.

    Follows migration chains (A→B→C) until finding the final destination.

    Args:
        mastodon_url: Full Mastodon profile URL (e.g., https://fosstodon.org/@pycon)
        max_depth: Maximum number of migration hops to follow (default: 5)

    Returns
    -------
    str | None
        New URL if migrated, None if no migration detected or on error.
    """
    parsed = parse_mastodon_url(mastodon_url)
    if not parsed:
        tqdm.write(f"Warning: Could not parse Mastodon URL: {mastodon_url}")
        return None

    visited = set()
    current_url = mastodon_url
    current_instance, current_username = parsed

    for _ in range(max_depth):
        # Detect circular migrations
        account_key = f"{current_username}@{current_instance}"
        if account_key in visited:
            tqdm.write(f"Warning: Circular migration detected for {mastodon_url}")
            break
        visited.add(account_key)

        # Query the Mastodon API
        api_url = f"https://{current_instance}/api/v1/accounts/lookup?acct={current_username}"
        headers = {"User-Agent": "Pythondeadlin.es Link Checker/0.1 (https://pythondeadlin.es)"}

        try:
            response = requests.get(api_url, headers=headers, timeout=10)

            if response.status_code == 404:
                tqdm.write(f"Warning: Mastodon account not found: {current_url}")
                return None

            if response.status_code == 429:
                tqdm.write(f"Warning: Rate limited by {current_instance}, skipping migration check")
                return None

            if response.status_code != 200:
                tqdm.write(f"Warning: Mastodon API error ({response.status_code}) for {current_url}")
                return None

            data = response.json()

            # Check if account has moved
            if data.get("moved"):
                moved_to = data["moved"]
                new_url = moved_to.get("url")
                if not new_url:
                    break

                tqdm.write(f"Mastodon migration detected: {current_url} → {new_url}")
                current_url = new_url

                # Parse the new URL for the next iteration
                new_parsed = parse_mastodon_url(new_url)
                if not new_parsed:
                    # If we can't parse the new URL, return it anyway
                    return new_url
                current_instance, current_username = new_parsed

                # Rate limit: wait 1 second between API calls
                time.sleep(1)
            else:
                # No migration, we've reached the final destination
                break

        except requests.RequestException as e:
            tqdm.write(f"Warning: Error checking Mastodon migration for {current_url}: {e}")
            return None

    # Return new URL only if it changed from the original
    if current_url != mastodon_url:
        return current_url
    return None
