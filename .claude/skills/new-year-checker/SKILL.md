---
name: new-year-checker
description: Looks for the next edition of a conference series that has only past editions and returns a new entry, a lead or a legacy suspect. Use when the desk hands over a worklist item whose skill is new-year-checker (stale series, missing editions, signals about archived series).
---

# New-year checker

The desk hands you one series whose editions are all past (`latest_edition` is the newest), plus the queue items that point at it. Find its next edition and return change sets in the shape AGENTS.md "Change sets" gives. You research; the desk edits the data. Field, name and evidence rules are in AGENTS.md.

## Steps

1. **Load** every edition of the series from all three data files, by `conference` and `alt_name`. When one turns out to be upcoming, return `no-change` naming it.
   Done when: you know the latest edition's year, `link`, `cfp_link`, CfP platform slug and socials.
2. **Search**, cheapest first, noting each outcome:
   - year variants of the latest `link` and `cfp_link`: the year moved on in the path or subdomain (`/2026/` to `/2027/`, `2026.` to `2027.`);
   - the site's home page and navigation;
   - the official accounts (`twitter`, `mastodon`, `bluesky`, `youtube`), for posts announcing dates or a CfP;
   - pretalx and Sessionize pages for the next year, guessed from past slugs (`https://pretalx.com/<slug>-<year>/`, `https://sessionize.com/<slug>-<year>/`);
   - the queue items' URLs and payloads.
   Done when: every source above was tried and its outcome noted.
3. **Decide** the series' outcome:
   - A primary source states exact `start` and `end` dates: `new-edition` with a full entry. `year` is the year of `start`. Carry over the stable fields (`conference`, `alt_name`, `sub`, the socials), citing the latest edition. Take `link`, `place`, `cfp`, `cfp_link` and the sub-links from this edition's sources, and `timezone` only when they state one. `cfp` is `TBA` until a deadline is published and `None` when the source says there is no public CfP.
   - The edition is announced but its dates are vague or missing: `lead`, with the URL and quote.
   - Nothing found: `no-change`, listing what was tried.
   - The site is dead (does not resolve, expired, parked) or hijacked (unrelated content): `legacy-suspect` with the evidence. The data stays as it is; `utils/sort_yaml.py` owns the legacy split.
   Done when: the series has exactly one of these outcomes.
4. **Fill past editions.** Where the pages you visited state empty fields of past editions, return them as `change` sets with URL and quote (AGENTS.md "Complete data").
   Done when: every empty field you saw stated has a change.
5. **Return** every change set. Flag a missing CoC (`no-coc`) and pages that did not render.
