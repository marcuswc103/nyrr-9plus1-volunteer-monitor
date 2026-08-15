# NYRR 9+1 Volunteer Spot Monitor

Watches specific `events.nyrr.org` volunteer-registration pages every 30
minutes and sends a phone push notification the instant a 9+1-eligible
volunteer role becomes `AVAILABLE` (usually from a cancellation). See
`OVERVIEW.md` and `SPEC.md` for the full why/what and technical spec.

The tool never logs in to NYRR, never stores NYRR credentials, and never
registers you for anything — it only watches and notifies. You still click
the link and register yourself.

## Setup

### 1. Create a free ntfy topic

[ntfy.sh](https://ntfy.sh) is a free push-notification service — no
account needed. A "topic" is just a name that acts like a private
broadcast channel; anyone who knows the exact name can publish or
subscribe to it, so **pick something unguessable**, e.g.
`nyrr-9plus1-yourname-x7k2`.

### 2. Install the ntfy app and subscribe

- Install **ntfy** from the App Store / Google Play.
- Open it, tap "+", and subscribe to the exact topic name you picked.
- You should now receive anything published to that topic, on this phone.

### 3. Add the topic as a GitHub secret

In this repo on GitHub: **Settings → Secrets and variables → Actions →
New repository secret**.
- Name: `NTFY_TOPIC`
- Value: the topic name you picked in step 1

The workflow reads it as `secrets.NTFY_TOPIC` — it's never written into
any file in this repo.

### 4. Test notifications end-to-end

Before relying on the schedule, confirm your phone actually receives
pushes:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
NTFY_TOPIC=your-topic-name python notify.py --test
```

You should get 3 pushes: an urgent "9+1 SPOT OPEN" test, a normal
"manual check needed" reminder test, and a high-priority "MONITOR BROKEN"
canary test.

### 5. Push this repo to GitHub and let the schedule run

`.github/workflows/monitor.yml` runs `main.py` every 30 minutes
automatically once this repo lives on GitHub with the `NTFY_TOPIC` secret
set — no further action needed. You can also trigger it manually anytime
from the **Actions** tab ("Run workflow").

## Adding or pausing a race

Edit `config/races.yaml`:

```yaml
races:
  - race_id: some-new-race
    name: "Some New Race"
    url: "https://events.nyrr.org/some-new-race-volunteers"
    robots_allowed: null   # filled in by discovery.py, don't guess this
    active: true
```

- **New race:** add an entry like the one above, then run
  `python discovery.py` once to fill in the real `robots_allowed` value
  from that race's actual robots.txt (never hand-edit that field).
- **Pause a race** (e.g. you already registered for a slot on it): set
  `active: false`. `scraper.py` and `main.py` skip inactive races
  entirely; the race stays in the file so you can reactivate it later.
- If `discovery.py` ever reports **more than 5** robots-blocked races
  across your full list, stop and rethink the approach before adding
  more (see `SPEC.md`'s "Decision gate") — the hybrid reminder design
  doesn't scale past that.
- If any race ever comes back `robots_allowed: false`, also create
  `.github/workflows/reminder.yml` (not present yet, since 0 of the
  current 4 races are blocked) to run `reminder_main.py` 3x/day — copy
  the pattern from `monitor.yml`, using `schedule` crons approximating
  7:30am/noon/5pm ET (GitHub Actions cron is UTC-only, so adjust the
  hours by 1 across EST/EDT transitions in March/November).

## Files

| File | Purpose |
|---|---|
| `discovery.py` | Manual, one-off: checks robots.txt and saves real page HTML/network traffic for a race. Run this after adding a new race. |
| `scraper.py` | Parses the current opportunity cards for all active, robots-allowed races and applies the 9+1/AVAILABLE/no-background-check match. |
| `state.py` | Tracks which roles currently match, per race, in `state.json`; diffs so only newly-opened roles trigger a notification. |
| `notify.py` | Sends pushes via ntfy.sh. Run `python notify.py --test` to verify delivery. |
| `main.py` | The scheduled entry point: scrape → diff → notify → save state. |
| `reminder_main.py` | Sends the robots-blocked reminder, if any races are blocked; otherwise no-ops. |
| `config/races.yaml` | The list of races being watched. |
| `state.json` | Committed back to the repo after each run — the monitor's memory of what's currently open. |
