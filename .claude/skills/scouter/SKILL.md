---
name: scouter
description: Discovers Python conference series the data does not track and proposes evidenced entries for the critic. Use when the desk hands over a worklist item whose skill is scouter (the daily scout item, importer candidates, registry changes, maintainer requests for a series the data lacks).
---

# Scouter

The desk hands you the daily `scout` item, or an item about a series no data file matches (an importer `candidate`, a `registry` change or a `maintainer-request`, with the queue items behind it). Find series worth listing that the data does not track and return change sets in the shape AGENTS.md "Change sets" gives. You research; the desk sends every proposal and lead you return to the critic, then edits the data. Listing, name and evidence rules are in AGENTS.md.

## Steps

1. **Gather finds.**
   - A `candidate` or `registry` item: the payload's names, fields and `evidence_url` are the find. A candidate's `flags`:
     - `lead-only`: an aggregator lead. Copy no value from it; take every value from a primary source.
     - `no-website`: the shared sheet has this edition but no website. Search for one.
     - `denylist-review: <domain>: <reason>`: the domain is on the denylist's `review` list. Copy the flag into the `flags` of the find's change set; the critic returns needs-maintainer.
   - A `maintainer-request` item: the series and URLs the comment names are the find, and the request settles its scope (step 2).
   - The `scout` item: search each of these, with `<year>` standing for this year and next (the year of the worklist's `today`, which the desk gives with the item).
     - Targeted web searches: "PyCon <year>", "PyData <year>", "Python conference call for proposals", "PyDay", "Python Pizza", framework and scientific library names with "conference", and the same in other languages ("conferencia Python", "Python Konferenz").
     - Bluesky public search, which answers its first page without authentication: `https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=<query>` (try `pycon <year>`, `"call for proposals" python`, `pydata <year>`).
     - pretalx and Sessionize event pages, found by web search (`site:pretalx.com python <year>`, `site:sessionize.com pycon`).
     - Regional community event sites: national Python associations, PyLadies chapters, PyData chapter pages.
   Done when: every source type was searched and each find is listed with the URL it came from.
2. **Scope.** Check each find against AGENTS.md "What gets listed".
   Done when: each find is in scope, or dismissed with the reason.
3. **Untracked check.** Apply AGENTS.md "Names": search the find's name, ignoring case and accents, in `conference` and `alt_name` across all three data files and in the keys and variations of `utils/tidy_conf/data/titles.yml`; grep the data files for its link's domain and compare each entry found by name and path. A domain match alone never makes a find tracked.
   Done when: each find is untracked, or dismissed as tracked, naming the entry it matched and whether by name or by link.
4. **Propose.** Follow each remaining find to its primary sources (an aggregator is a lead, never the evidence) and name it per AGENTS.md "Names".
   - Exact `start` and `end` dates: `new-series` with a full entry and every field's URL and quote, plus one `new-series` set per past edition the sources date exactly (AGENTS.md "Complete data").
   - Otherwise: `lead`, with what is known and where it is stated.
   Done when: every remaining find is a `new-series` or a `lead`.
5. **Return** every change set, the dismissed finds included as `no-change` with their reason so the desk can ledger them. Flag a missing CoC (`no-coc`) and pages that did not render.
   Done when: every find from step 1 is in the change sets you return: a dismissed find or a lead in exactly one, a new series in one per edition.
