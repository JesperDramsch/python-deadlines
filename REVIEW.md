# Review instructions

The "PR review" Routine reads this file from the base branch of every pull request to this repository. The contract in claude-tools [`coding/skills/review/SKILL.md`](https://github.com/JesperDramsch/claude-tools/blob/main/coding/skills/review/SKILL.md) sets what counts as a finding and the shape of the review; this file says what matters here. Keep it short: every line competes with the contract for the reviewer's attention.

## Important here

- A conference entry whose `cfp`, `start`, `end`, `place` or `link` disagrees with the conference's own website: fetch `link` (and `cfp_link`) and compare. The schema checks formats, not facts, and the site publishes whatever is merged.
- A `year` that differs from the year of `start`, or a `timezone` that is not an IANA name: the schema accepts both, and `static/js/countdown-simple.js` then falls back to the visitor's own zone without saying so.
- An entry that already exists in `_data/conferences.yml`, `_data/archive.yml` or `_data/legacy.yml` under another spelling of the name. CI only warns, and only on an exact name-and-year match.
- A change under `_layouts/`, `_includes/` or `_pages/` that names an include, layout or asset path that does not exist: no pull-request job builds the site for those paths, so the first failure is the deploy of `main`.
- A `utils/` change that lets `sort_yaml.py` write a data file after a validation error, or drop an entry on the way. The weekly sort ([recurring-sort.yml](.github/workflows/recurring-sort.yml)) merges its own result unattended.

## Leave alone

- Everything `pixi run sort` enforces or rewrites: the pydantic schema in `utils/tidy_conf/schema.py` (required fields, date and URL formats, `sub` against `_data/types.yml`, a location for in-person events), key order, sort order, years inside `conference`, redundant link fields and geocoding. After a merge, [pr-sort.yml](.github/workflows/pr-sort.yml) opens the clean-up PR itself.
- Everything `pixi run pre` enforces on Python: ruff, black, isort, pyupgrade, docsig and the pre-commit-hooks set. Quote their output under Tests.
- JavaScript style in `static/js/`: ESLint runs with `|| true`; the jest coverage thresholds in `jest.config.js` are the only enforced bar.
- Translations under `_i18n/` other than `en`: Crowdin owns them ([crowdin.yml](crowdin.yml), [TRANSLATION.md](TRANSLATION.md)), and a direct edit is overwritten by the next sync.

## Checks

There is no `pixi` in the Routine sandbox, so run the same checks through `uv`, pinned the way `pixi.toml` pins them (Python 3.11, pandas 2.2):

- Data: `uv run --python 3.11 --with "pandas<2.3",pyyaml,pydantic,pytz,thefuzz,iso3166,icalendar,tqdm,requests python utils/sort_yaml.py --skip_links`, then `git diff --stat -- _data`. A non-zero exit is a finding; a diff is the rewrite the post-merge sort will do, not a finding.
- Python, when `utils/` or `tests/` change: `uv run --python 3.11 --with "pandas<2.3",pytest,pytest-mock,freezegun,hypothesis,responses,pyyaml,pydantic,pytz,thefuzz,iso3166,icalendar,tqdm,requests pytest tests/ -q -x -p no:cacheprovider`.
- Lint, when Python changes: `uvx ruff@0.4.4 check utils tests`, the version `.pre-commit-config.yaml` pins (a newer ruff reports dozens of pre-existing errors). The rest of the pre-commit set is the `pre-commit.ci - pr` status on the PR: quote it, do not rerun it.
- JavaScript, when `static/js/` or `tests/frontend/` change: `npm ci && npm test`.
