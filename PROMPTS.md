# Claude Code Prompts — NYRR 9+1 Volunteer Monitor (v2)

Run these **in order**, in a fresh git repo, one prompt per session. Put
`SPEC.md` in the repo root before Prompt 1 — tell Claude Code to read it
first each time.

**Do not skip the manual checkpoint after Prompt 1.** Discovery's robots.txt
count decides whether this build even proceeds as designed (see SPEC.md
"Decision gate"). Don't let Claude Code guess past that gate.

---

## Prompt 1 — Scaffold + Discovery

```
Read SPEC.md in this repo before doing anything else.

Set up the project structure described in SPEC.md using Python. Then
build ONLY the discovery script (discovery.py) described in section
"2. Discovery script":

Put these 4 real race URLs into config/races.yaml as the starting list
(race name can be inferred from the slug for now):
- https://events.nyrr.org/tcs-new-york-city-marathon-start-volunteers
- https://events.nyrr.org/race-to-deliver-4m-to-benefit-god-s-love-we-deliver-volunteers
- https://events.nyrr.org/nyrr-ted-corbitt-15k-volunteers
- https://events.nyrr.org/nyrr-frosty-5k-volunteers

discovery.py must:
- For each URL, check robots.txt for events.nyrr.org via
  urllib.robotparser BEFORE doing anything else with that URL.
- Never fetch/render a URL robots.txt disallows. Log it as blocked
  instead.
- For allowed URLs: load the page with Playwright (headless Chromium),
  capture every XHR/fetch network request and response (especially
  JSON), and save them to discovery_output/<race_id>/. Also save the
  fully-rendered HTML and a full-page screenshot there.
- Specifically look for: (a) any API response containing role name,
  AVAILABLE/ALL SPOTS FILLED status, and tag list (9+1 / No +1 /
  possibly a background-check tag) per opportunity, and (b) whether
  each opportunity card has its own unique URL, anchor, or ID we could
  deep-link to.
- Print a clear final summary: how many of the 4 URLs are auto-
  checkable vs. robots-blocked (state the count explicitly against the
  5-page threshold from SPEC.md's "Decision gate"), and whether a
  usable structured data source (API or clean HTML) was found.

Set up requirements.txt / a venv and confirm Playwright's browser
binaries install correctly. Don't build the scraper or notifier yet —
this prompt is discovery only.
```

**STOP after this prompt. Run `discovery.py` yourself and read the
summary.**
- If **more than 5** of your real target races come back robots-blocked,
  stop here and come back to me (Claude, in chat) with the count before
  writing any more code — per SPEC.md, the hybrid design doesn't hold at
  that scale and we need to rethink the approach.
- If **5 or fewer** are blocked (very possibly zero, since this is a
  different platform than the one that showed a block earlier), continue
  to Prompt 2. Also open `discovery_output/` and confirm you can see, for
  at least one race, the actual field names/markup for status, the 9+1
  tag, and (if it exists) a background-check tag — you'll paste the
  relevant bit into Prompt 2.

---

## Prompt 2 — Build the real scraper

```
Read SPEC.md again. Here's what discovery.py found on the real
events.nyrr.org pages: [PASTE YOUR DISCOVERY FINDINGS HERE — the JSON
API response shape if one was found, OR the relevant HTML snippet
showing an AVAILABLE+9+1 card vs. an ALL SPOTS FILLED or No+1 card.
Also paste the exact wording of any "background check required"-style
tag if you saw one, and whether individual opportunities have their
own deep-linkable URL/anchor.]

Update config/races.yaml so each race has an explicit
robots_allowed: true/false field set from discovery.py's actual
findings (not guessed).

Build scraper.py per SPEC.md section "3. Poll/scrape script":
- Only ever touches races where robots_allowed: true.
- For each: return a list of opportunity cards with role name, status,
  tags, and best available link (deep link if one exists, else the
  race page URL).
- Apply the three-part match from SPEC.md "Match criteria": status =
  AVAILABLE, tags include "9+1", tags do NOT include the background-
  check tag.
- Use the API directly if discovery found one (faster, lighter) rather
  than re-rendering with Playwright on every scheduled run; only use
  Playwright at runtime if there's genuinely no API.
- Write a test using a saved sample response from discovery_output/ so
  parsing logic can be tested without hitting the live site.

Also build state.py: load/save state.json (which role names currently
match per race), and a diff function returning only NEWLY-matching
roles since the last run (not roles that already matched last time),
plus any races that errored during scraping.
```

---

## Prompt 3 — Notifications

```
Read SPEC.md section "5. Notifier". Build notify.py using ntfy.sh:
- Read the ntfy topic from environment variable NTFY_TOPIC (never
  hardcode it).
- send_opening_alert(race_name, role_name, link): urgent priority,
  title "9+1 SPOT OPEN: <role_name> (<race_name>)", the link as the
  click-through action so tapping the notification opens it directly.
- send_robots_blocked_reminder(list of {race_name, link}): normal
  priority, one push listing all currently robots-blocked races with
  links (only relevant if config has any robots_allowed: false races
  — if none exist, this function should just no-op cleanly).
- send_canary_alert(race_name, error): distinct, unmissable alert
  meaning "the monitor broke, check this race manually," including the
  error detail.
- Add a --test flag to send one of each notification type so I can
  confirm my phone receives them before wiring up the schedule.

Wire main.py: run scraper.py on robots_allowed races -> diff via
state.py -> send_opening_alert for each newly-matching role ->
send_canary_alert for any scrape errors -> save updated state.json.
Print a clear run summary to stdout for reading in GitHub Actions logs.

Build reminder_main.py separately: if any races have
robots_allowed: false, call send_robots_blocked_reminder with all of
them; otherwise do nothing and exit cleanly.
```

---

## Prompt 4 — GitHub Actions schedules

```
Read SPEC.md section "6. Scheduler". Build two workflow files:

.github/workflows/monitor.yml:
- Trigger: workflow_dispatch, plus schedule "*/30 * * * *" (every 30
  minutes).
- Steps: checkout, set up Python, install requirements (only install
  Playwright browsers if scraper.py actually needs runtime rendering
  per what discovery found — skip that step entirely if we're hitting
  a direct API, to keep runs fast), run main.py with NTFY_TOPIC pulled
  from a GitHub Actions secret of the same name, then commit+push
  state.json only if it changed (bot commit identity; no-op cleanly if
  no diff).
- Grant contents: write permission for the push-back step.

.github/workflows/reminder.yml:
- Only create this file if config/races.yaml currently has at least
  one robots_allowed: false entry — otherwise skip creating it and
  say why in your response.
- Trigger: workflow_dispatch, plus three schedule crons approximating
  7:30am, 12:00pm, and 5:00pm US Eastern. Add a YAML comment noting
  GitHub Actions cron is UTC-only and these will drift ~1hr across
  EST/EDT transitions, with a note on where to adjust the hours twice
  a year.
- Steps: checkout, set up Python, install requirements, run
  reminder_main.py with NTFY_TOPIC from the same secret.

Add a README.md section: how to create a free ntfy topic and add it as
a GitHub secret, how to install the ntfy phone app and subscribe, and
how to edit config/races.yaml to add/pause races as new ones get
posted.
```

---

## Prompt 5 — Hardening pass

```
Review the whole repo against SPEC.md's "Respectful-use rules" and
"Non-goals":
- Confirm robots.txt is checked at runtime (not just once, hardcoded)
  everywhere a events.nyrr.org URL is fetched.
- Confirm no retry-loop could hammer the site on failure — one failed
  request should log + trigger the canary alert, not retry
  aggressively.
- Confirm the User-Agent is honest/identifiable, not spoofed.
- Confirm nothing logs in to NYRR, stores NYRR credentials, or
  auto-registers for a slot — notification only, always.
- Confirm state.json's diff logic actually suppresses repeat
  notifications for a role that was already open last run (re-test
  this specifically — it's easy to get backwards).
- Add error handling so one race's parsing failure doesn't crash the
  run or block checking the other races.
- Update README.md with complete end-to-end setup steps a future me
  (no memory of building this) could follow from scratch, including
  what to do if a new race needs to be added to config/races.yaml.
```
