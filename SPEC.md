# NYRR 9+1 Volunteer Spot Monitor — Technical Spec (v2)

## Goal
Detect the moment a **9+1-credit-eligible volunteer opportunity becomes
AVAILABLE** on NYRR's volunteer registration platform (typically from a
cancellation), and push an instant phone notification linking straight to
that specific opportunity — checked every 30 minutes, for free, on GitHub
Actions.

## Target platform (corrected)
Real target pages live on **`events.nyrr.org`**, e.g.:
- `events.nyrr.org/tcs-new-york-city-marathon-start-volunteers`
- `events.nyrr.org/race-to-deliver-4m-to-benefit-god-s-love-we-deliver-volunteers`
- `events.nyrr.org/nyrr-ted-corbitt-15k-volunteers`
- `events.nyrr.org/nyrr-frosty-5k-volunteers`

This is a **separate platform from the main `nyrr.org` marketing site** —
different app, likely different backend, and critically, **its own,
separate `robots.txt`**. Earlier research found a robots.txt block on a
page under `nyrr.org/info/...` — that finding does NOT automatically carry
over to `events.nyrr.org` and must be re-checked from scratch.

Each `events.nyrr.org` race page lists individual volunteer roles as cards,
each showing:
- A status badge: `AVAILABLE` (green) or `ALL SPOTS FILLED` (red)
- A role title (e.g. "Bag Check", "Course Marshal")
- A tag badge: `9+1` or `No +1` (possibly also `Background Check Required`
  or similar — unconfirmed, watch for it during discovery)
- A `Register` button when available
- Page-level "All Tags" filter dropdown and "Show Only Available Options"
  checkbox — this UI strongly suggests structured, filterable data behind
  the page (either an API response or well-tagged HTML), which is good
  news for reliable scraping.

## Match criteria (all three must be true to notify)
1. Status badge = `AVAILABLE` (not `ALL SPOTS FILLED`)
2. Tag includes `9+1` (not `No +1`)
3. Tag does **not** include `Background Check Required` (or equivalent —
   confirm exact label during discovery)

## Key risks / unknowns to resolve during discovery (don't guess — inspect)
- **Robots.txt for `events.nyrr.org`**: unverified — check first, before
  writing any scraper logic. If the target race pages are disallowed,
  stop and reconsider before building (see "Decision gate" below).
- Is there a clean JSON/API response backing these cards (likely, given
  the filter UI), or is it server-rendered HTML only?
- Does each opportunity card have its own unique URL/anchor/fragment we
  can deep-link to directly, or only the race page as a whole (in which
  case the notification links to the race page plus the role name as
  text, and the user finds it via the "Show Only Available Options"
  filter)?
- Exact tag label(s) to exclude beyond "9+1"/"No +1" — confirm the
  "background check required" wording verbatim from a real page.

## Decision gate — resolve before building the scheduled scraper
Check `robots.txt` against all real target URLs (start with the 4 above;
extend as more races get posted):
- **≤5 race pages disallowed** → hybrid design: auto-check every allowed
  page every 30 min (silent unless a match is found); for disallowed
  pages, send a standing reminder 3x/day (7:30am/noon/5pm ET) with direct
  links, so the user checks those few by hand.
- **>5 disallowed** → stop. The hybrid no longer scales — report back
  with the count and we pick a different approach (e.g. investigate
  whether a logged-in NYRR account/dashboard exposes a different,
  allowed view; an official notification feature; contacting NYRR) before
  writing more code.

## Architecture overview
```
[config/races.yaml] --lists--> [scraper.py] --checks--> [events.nyrr.org pages/API]
                                     |
                                     v
                          [state.json in repo] (diff vs last run)
                                     |
                    (a role newly matches all 3 criteria)
                                     v
                       [notify.py -> ntfy.sh] --> phone push w/ direct link
                                     |
                        (scrape failed / selector broke)
                                     v
                           [canary alert -> ntfy.sh]

Auto-checkable races: scheduled every 30 min via GitHub Actions cron.
Robots-blocked races (if any, up to 5): a 3x/day reminder push with links,
no scraping performed on these at all.
```

## Components

### 1. `config/races.yaml`
List of target races with: name, `events.nyrr.org` URL, whether robots.txt
allows auto-checking it (filled in by discovery, not guessed), active/
paused flag (mute a race once you've registered for it).

### 2. Discovery script (`discovery.py`, Playwright-based, run manually,
   not scheduled)
For each URL in config:
- Check `robots.txt` for `events.nyrr.org` via `urllib.robotparser` —
  this result gets written into `config/races.yaml`, not hardcoded
  elsewhere.
- For allowed URLs only: load the page in headless Chromium, capture all
  XHR/fetch requests+responses, save the rendered HTML, save a
  screenshot, all to `discovery_output/<race_id>/`.
- Print a summary: which pages are auto-checkable vs. robots-blocked
  (with a running count against the 5-page threshold), and whether a
  usable JSON API was found.

### 3. Poll/scrape script (`scraper.py`)
- Only touches races marked robots-allowed in config.
- Per race: get current list of volunteer opportunity cards (via API if
  found, else parsed rendered HTML) with, for each card: role name,
  status (`AVAILABLE`/`ALL SPOTS FILLED`), tag list, and the best
  available link (opportunity-specific if one exists, else the race page
  URL).
- Apply the three-part match criteria above.
- Output `{race_id: [matching_role, ...]}` — empty list if nothing
  currently matches.

### 4. State store (`state.json`, committed back to the repo)
- Holds, per race, the set of role names that currently match.
- Diff against previous run: only **newly**-matching roles trigger a
  notification (a role that already matched last run and still matches
  does not re-notify — avoids repeat pings while you're mid-registration).
- Committed via `git commit && push` with `GITHUB_TOKEN` (`contents:
  write` permission) at the end of each run; skip the commit if nothing
  changed, to avoid empty commits.

### 5. Notifier (`notify.py`)
- **ntfy.sh**, topic from `NTFY_TOPIC` GitHub secret (treat like a
  password).
- `send_opening_alert(race_name, role_name, link)`: urgent priority,
  title like `"9+1 SPOT OPEN: <role_name> (<race_name>)"`, body/click
  action = the direct link (opportunity-specific if available, else race
  page URL with role name called out in the message text).
- `send_robots_blocked_reminder([...])`: normal priority, 3x/day only,
  one push listing all robots-blocked races with their links, so the
  user can tap through and eyeball them manually.
- `send_canary_alert(race_name, error)`: distinct alert for scrape/parse
  failures — silent breakage is worse than no monitor.

### 6. Scheduler (`.github/workflows/monitor.yml`) — two workflows
- **`monitor.yml`**: `*/30 * * * *` (every 30 min) — runs `scraper.py` +
  diff + `send_opening_alert` for auto-checkable races only.
- **`reminder.yml`**: three crons approximating 7:30am/noon/5pm ET —
  runs only if there are robots-blocked races in config; sends
  `send_robots_blocked_reminder`. Skip creating this workflow entirely
  if discovery finds zero blocked races.
- Both: note in a YAML comment that GitHub Actions cron is UTC-only and
  drifts ~1hr across EST/EDT transitions; flag where to adjust twice a
  year.
- Both include `workflow_dispatch` for manual runs.

### 7. Respectful-use rules (in code, not just docs)
- Never scrape a robots.txt-disallowed URL, ever — checked at runtime
  each run, not just once at setup.
- One request per race per check, no retry loops.
- Honest, identifiable User-Agent string.
- 30-min cadence for auto-checked races is the ceiling — don't increase
  without deliberately revisiting this decision.

## Non-goals
- No auto-registration/auto-claiming — notify only. The user completes
  registration manually; the tool never touches NYRR login credentials
  or payment details.
- No monitoring of race *registration* (running) slots — 9+1-tagged
  volunteer roles only.

## Notification examples (for reference when building notify.py)
- Opening found: `9+1 SPOT OPEN: Bag Check (Ted Corbitt 15K) - tap to
  register: <link>`
- Robots-blocked reminder (3x/day, only if any exist): `Manual check
  needed (auto-monitoring blocked): Race A <link>, Race B <link>`
- Canary: `Monitor broken for <race>: <error>. Check manually: <link>`
