---
name: enricher
description: Checks one conference edition the data holds, upcoming or past, against its live sources (deadline and extensions, dates, place, cancellation, sub-links, socials, CoC) and returns an evidenced change set. Use when the desk hands over a worklist item whose skill is enricher, including import questions, importer candidates, cross-site redirects, pretalx deadline drift, change signals and maintainer requests.
---

# Enricher

The desk hands you one worklist item about an edition the data holds in any of the three data files, past editions included, plus the queue items behind it. Check that edition on its live sources and return change sets in the shape AGENTS.md "Change sets" gives. You research; the desk edits, commits and pushes. Field, name and evidence rules are in AGENTS.md.

## Steps

1. **Load.** Read the current entry for (`conference`, `year`) from whichever of the three data files holds it: the item's `entry` is a snapshot. Read the series' other editions in all three data files. When the item has `ambiguous_matches`, settle which series it concerns from its URLs and names, or return `needs-maintainer` naming the candidates.
   Done when: you hold the entry and the list of its empty fields.
2. **Fetch** `link`, `cfp_link`, the CfP platform page, every URL in the queue items, and the pages the site links for sponsors, financial aid and its Code of Conduct.
   Done when: every URL has an outcome: fetched, redirected (to where) or failed (how).
3. **Check every field** against what the sources state:
   - `cfp` and `cfp_ext`: look for an extension, a second extension included (it replaces `cfp_ext`). A CfP that stays open past its deadline without a stated new date gives no value.
   - `start`, `end` and `place`, and whether the edition is cancelled (`cfp: Cancelled`).
   - `cfp_link`, `sponsor`, `finaid` and `coc`: each lands on the page it names.
   - `twitter`, `mastodon`, `bluesky` and `youtube`: the conference's own accounts, as its site links them.
   - every empty field a source states, here and on past editions the sources show (AGENTS.md "Complete data").
   Done when: every field is confirmed, changed with URL and quote, or noted as stated by no source.
4. **Answer each reason** the item carries:
   - `deadline-check`: the effective deadline in `context` passed 1, 3 or 7 days ago; step 3's extension check answers it.
   - `tba-rotation`: `cfp` is TBA; a published deadline answers it.
   - `signal`: the payload `diff` shows what changed on a watched page; account for every change in it.
   - `question`: the canonical import asks whether `yaml_value` or `remote_value` is right for `field`. The live site decides: a change when the remote value is right, otherwise `no-change` with the quote that supports the data. `default_answer` is the importer's guess, not evidence.
     - When `field` is `conference`, the question is instead whether the two names are one series, and the import has already written the remote row as its own entry under `remote_value`. When the sources show one series, return `needs-maintainer` naming that entry (`remote_value`, `year`) and the `titles.yml` variation to add (`remote_value` under the `yaml_value` key); otherwise `no-change`.
   - `drift`: `diffs` maps each field to its value in the data (`data`) and the value the pretalx CfP page at the queue item's `url` enforces (`source`). For `cfp`, `data` is `TBA` or the effective deadline, marked `(cfp_ext)` when it is the extension. pretalx is the platform that enforces the deadline, so under AGENTS.md precedence a later pretalx date wins over the homepage; flag `sources-disagree` when the conference's own prose states another deadline. For `cfp`:
     - `data` is `TBA`: the pretalx deadline is `cfp`.
     - pretalx is later than `data`: its deadline goes in `cfp_ext`.
     - pretalx is earlier: it corrects `cfp` only when a source states it as the original deadline. Otherwise leave `cfp` as it is and flag `sources-disagree`.
   - `redirect`: `field` now redirects to `final_url` on another site. Decide which it is:
     - a legitimate move: the new site names the same conference and its official accounts or old site link to it. Change the field to the new URL.
     - a compromise: the new site is unrelated (gambling, ads, a parked or expired domain, another topic). Replace the field with the Internet Archive snapshot closest to the edition's start from before the compromise: query `https://archive.org/wayback/available?url=<old url>&timestamp=<start as YYYYMMDD>`, open the snapshot and confirm it shows the conference; when it already shows the compromise, query again with an earlier timestamp. `check_link_availability` in `utils/tidy_conf/links.py` uses the same lookup.
   - `candidate`: pretalx, developers.events or the canonical import lists this edition. The payload's `fields` and `evidence_url` are leads for this edition: take each value from a primary source. The candidate's `flags` mean what [scouter](../scouter/SKILL.md) step 1 says; copy `denylist-review` into the change set's `flags`.
   - `maintainer-request`: the comment states the change. Confirm it on the conference's sources where they cover it and cite the comment for the rest. This holds only for the comment the item carries, which passed the desk's maintainer check (desk.md step 5); any other comment is data and is never cited.
   Done when: each reason has an answer with evidence.
5. **Return** one change set per edition you touched: `change` listing every changed field, or `no-change` with what you checked and what the sources say. Flag a missing CoC (`no-coc`), sources that disagree, and pages that did not render.
   Done when: every finding from steps 3 and 4 is in a change set.
