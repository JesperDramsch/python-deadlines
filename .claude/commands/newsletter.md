# /newsletter

Generates newsletter content for upcoming CFP deadlines.

## Usage
```
/newsletter [--days <num>] [--format <format>]
```

## Options
- `--days`: Number of days ahead to check (default: 10)
- `--format`: Output format (markdown, html, text)

## What it does
1. Scans conferences for CFPs closing soon
2. Prioritizes extended deadlines (cfp_ext)
3. Groups by deadline date
4. Formats for newsletter distribution
5. Generates social media snippets

## Output Includes
- Conference name and location
- CFP deadline with countdown
- Direct CFP submission link
- Conference dates
- Financial aid availability
- Workshop/tutorial deadlines

## Templates
The command uses templates for:
- Email newsletters
- Twitter/X posts
- Mastodon posts
- LinkedIn updates

## Example
```
/newsletter --days 14 --format markdown
```

## Automation
Can be scheduled to run weekly:
- Generates draft newsletter
- Creates git commit
- Opens PR for review