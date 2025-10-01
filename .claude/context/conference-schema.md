# Conference Data Schema Reference

## Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `conference` | string | Conference name | "PyCon US" |
| `year` | integer | Conference year (>= 1989) | 2025 |
| `link` | url | Main conference website | "https://pycon.org" |
| `cfp` | datetime | CFP deadline | "2025-01-15 23:59:59" |
| `place` | string | Location (city, country) | "Pittsburgh, PA, USA" |
| `start` | date | Conference start date | "2025-05-15" |
| `end` | date | Conference end date | "2025-05-20" |
| `sub` | array | Submission types | ["talks", "workshops"] |

## Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `cfp_link` | url | Direct CFP submission link | "https://cfp.pycon.org" |
| `cfp_ext` | datetime | Extended CFP deadline | "2025-01-30 23:59:59" |
| `workshop_deadline` | datetime | Workshop submission deadline | "2025-02-01 23:59:59" |
| `tutorial_deadline` | datetime | Tutorial submission deadline | "2025-02-01 23:59:59" |
| `timezone` | string | IANA timezone (default: AoE) | "America/New_York" |
| `sponsor` | array | Sponsorship tiers | ["diamond", "gold"] |
| `finaid` | boolean/date | Financial aid available | true or "2025-01-01" |
| `twitter` | string | Twitter/X handle (no @) | "pycon" |
| `mastodon` | url | Mastodon profile URL | "https://fosstodon.org/@pycon" |
| `bluesky` | url | Bluesky profile URL | "https://bsky.app/profile/pycon.org" |
| `note` | string | Additional notes | "Virtual attendance available" |
| `location` | object | Coordinates | {lat: 40.4406, lon: -79.9959} |
| `extra_places` | array | Additional locations (hybrid) | ["Online", "Berlin, Germany"] |

## Validation Rules

### Dates
- Format: `YYYY-MM-DD HH:mm:ss` (time optional)
- Year must be >= 1989 (Python's birth year)
- `end` must be after `start`
- `cfp` should be before `start`
- `cfp_ext` must be after `cfp`

### URLs
- Must use HTTPS protocol
- Must be valid, accessible URLs
- No trailing slashes

### Coordinates
- Latitude: -90 to 90
- Longitude: -180 to 180
- Maximum 5 decimal places precision

### Timezones
- Must be valid IANA timezone
- Examples: "America/New_York", "Europe/Berlin", "Asia/Tokyo"
- Default: "AoE" (Anywhere on Earth) = UTC-12

### Submission Types
Valid values for `sub` array:
- `talks` - Regular conference talks
- `workshops` - Hands-on workshops
- `tutorials` - Educational tutorials
- `posters` - Poster presentations
- `lightning` - Lightning talks
- `panels` - Panel discussions
- `keynotes` - Keynote submissions (rare)

## Conference Types

Defined in `_data/types.yml`:
- `PY` - General Python conferences
- `SCIPY` - Scientific Python
- `DATA` - Data science focused
- `WEB` - Web development (Django, Flask)
- `BIZ` - Business/Enterprise Python
- `GEO` - Geospatial Python
- `EDU` - Education focused
- `REGIONAL` - Regional/local events

## Example Entry

```yaml
- conference: PyCon US
  year: 2025
  link: https://us.pycon.org/2025/
  cfp: '2024-12-15 23:59:59'
  cfp_link: https://us.pycon.org/2025/speaking/
  cfp_ext: '2025-01-05 23:59:59'
  workshop_deadline: '2025-01-15 23:59:59'
  place: Pittsburgh, PA, USA
  location:
    lat: 40.4406
    lon: -79.9959
  start: '2025-05-14'
  end: '2025-05-22'
  sponsor:
    - diamond
    - gold
    - silver
  sub:
    - talks
    - tutorials
    - workshops
    - posters
  timezone: America/New_York
  twitter: pycon
  mastodon: https://fosstodon.org/@pycon
  finaid: '2025-02-01'
  note: Hybrid event with online attendance option
  extra_places:
    - Online
```