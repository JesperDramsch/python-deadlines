---
name: scouter
description: Discovers Python conference series the data does not track and proposes evidenced entries for the critic. Use when the desk hands over a worklist item whose skill is scouter (the daily scout item, importer candidates, registry changes).
---

# Scouter

The desk hands you the daily `scout` item, or an item about a series no data file matches (an importer `candidate` or a `registry` change, with the queue items behind it). Find series worth listing that the data does not track and return change sets in the shape AGENTS.md "Change sets" gives. You research; the desk sends every proposal and lead you return to the critic, then edits the data. Listing, name and evidence rules are in AGENTS.md.

## Steps

1. **Gather finds.**
   - A `candidate` or `registry` item: the payload's names, fields and `evidence_url` are the find.
   - The `scout` item: search each of these.
     - Targeted web searches: "PyCon 2027", "PyData 2027", "Python conference call for proposals", "PyDay", "Python Pizza", framework and scientific library names with "conference", and the same in other languages ("conferencia Python", "Python Konferenz").
     - Bluesky public search, which answers its first page without authentication: `https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=<query>` (try `pycon 2027`, `"call for proposals" python`, `pydata 2027`).
     - pretalx and Sessionize event pages, found by web search (`site:pretalx.com python 2027`, `site:sessionize.com pycon`).
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
