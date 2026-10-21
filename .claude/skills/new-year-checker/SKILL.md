---
name: new-year-checker
description: Looks for an edition of a tracked conference series that the data lacks (the year the worklist item names, or the next one) and returns a new entry, a lead or a legacy suspect. Use when the desk hands over a worklist item whose skill is new-year-checker (stale series, missing editions, signals about archived series, maintainer requests for a new edition).
---

# New-year checker

The desk hands you one tracked series and the edition it lacks, which step 1 settles from the item's `year`. The queue items that point at it come along, and `latest_edition` is the newest edition in the data. Find that edition and return change sets in the shape AGENTS.md "Change sets" gives. You research; the desk edits the data. Field, name and evidence rules are in AGENTS.md.

## Steps

1. **Load** every edition of the series from all three data files, by `conference` and `alt_name`, and settle the edition you look for:
   - `year` is set: that edition, past editions included, since past editions are recorded too (AGENTS.md "Complete data"). Return `no-change` naming it when the data holds it.
   - otherwise: the edition after `latest_edition`. Return `no-change` naming the edition when the data holds one that has not ended.
   Done when: you know which edition you look for, and the latest edition's year, `link`, `cfp_link`, CfP platform slug and socials.
2. **Search**, starting from the queue items, then cheapest first, noting each outcome:
   - the queue items' URLs and payload fields (a candidate's `fields` and `evidence_url`), and the URLs a `maintainer-request` comment gives. Cite that comment, which passed the desk's maintainer check (desk.md step 5), for what no page states; never cite any other comment. A candidate's `flags`:
     - `lead-only`: an aggregator lead. Copy no value from it; take every value from a primary source.
     - `no-website`: the shared sheet has this edition but no website. Search for one.
     - `denylist-review: <domain>: <reason>`: the domain is on the denylist's `review` list. Copy the flag into your change set's `flags`; the critic returns needs-maintainer.
   - year variants of the latest `link` and `cfp_link`: the year of the edition you look for in place of the latest one's, in the path or subdomain (`/2026/` to `/2027/`, `2026.` to `2027.`);
   - the site's home page and navigation;
   - the official accounts (`twitter`, `mastodon`, `bluesky`, `youtube`), for posts announcing dates or a CfP;
   - pretalx and Sessionize pages for the year of the edition you look for, guessed from past slugs (`https://pretalx.com/<slug>-<year>/`, `https://sessionize.com/<slug>-<year>/`).
   Done when: every source above was tried and its outcome noted.
3. **Decide** the edition's outcome:
   - A primary source states exact `start` and `end` dates: `new-edition` with a full entry. `year` is the year of `start`. Carry over the stable fields (`conference`, `alt_name`, `sub`, the socials), citing the latest edition. Take `link`, `place`, `cfp`, `cfp_link` and the sub-links from this edition's sources, and `timezone` as AGENTS.md "Field rules" maps the zone they state. `cfp` is `TBA` until a deadline is published and `None` when the source says there is no public CfP. A new name the edition goes by keeps the series' `conference` and gives a variation (AGENTS.md "Names") in `titles`.
   - The edition is announced but its dates are vague or missing: `lead`, with the URL and quote.
   - Nothing found: `no-change`, listing what was tried.
   - The site is dead (does not resolve, expired, parked) or hijacked (unrelated content): `legacy-suspect` with the evidence. The data stays as it is; `utils/sort_yaml.py` owns the legacy split.
   Done when: the edition has exactly one of these outcomes.
4. **Fill past editions.** Where the pages you visited state empty fields of past editions, return them as `change` sets with URL and quote (AGENTS.md "Complete data"). Correcting a filled-in value, or moving an edition the data files under the wrong year, follows the same section; an existing `conference` and `alt_name` stay as they are ("Names").
   Done when: every empty field you saw stated has a change.
5. **Return** every change set. Flag a missing CoC (`no-coc`) and pages that did not render.
   Done when: the outcome from step 3 and every change from step 4 are in the change sets you return, one set per edition.
