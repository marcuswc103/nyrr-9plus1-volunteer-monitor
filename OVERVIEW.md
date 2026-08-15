# Project Overview — NYRR 9+1 Volunteer Spot Monitor

Give this file to Claude Code alongside `SPEC.md` (technical spec) and
`PROMPTS.md` (the exact build prompts, in order). This file is the "why
and what," in plain terms, for context — read it first.

## The real-world problem
I'm doing New York Road Runners' **9+1 program**: complete nine
9+1-credit-eligible races plus one 9+1-credit-eligible **volunteer shift**
in 2026, and I get guaranteed entry into the **2027 TCS New York City
Marathon**.

The races are the easy part. The volunteer credit is the bottleneck:
volunteer slots for 9+1-eligible roles fill up almost immediately when
they're posted, and the next scheduled mass-opening isn't until
**September 8, 2026** (TCS NYC Marathon Week opportunities). That's a big,
competitive opening I don't want to rely on alone.

However, spots also **reopen** throughout the year whenever someone who
already registered cancels — NYRR's own help docs confirm this happens
automatically online, with no waitlist mechanism. This already happened
once, on a race I was watching, when several people cancelled and their
slots reappeared. That's the gap I'm trying to close: I can't refresh
these pages manually all day, so I need something that watches for me and
tells me the instant a real opening appears.

## What "done" looks like
A free, automated system that:
1. Checks specific `events.nyrr.org` volunteer pages **every 30
   minutes**.
2. Recognizes a genuinely useful opening — see exact criteria below —
   not just any page change.
3. Sends me a **phone push notification the moment a match appears**,
   with a link I can tap straight through to log in and register.
4. Does **not** spam me with repeat notifications for something that's
   already been open for a while and I haven't acted on yet — only new
   openings trigger a push.
5. Costs nothing to run.

## The exact opportunities I'm looking for
On each race's `events.nyrr.org` volunteer page, opportunities are listed
as individual cards. Each card shows a status badge and one or more tag
badges. I only want to be notified about a card that is **all three** of
the following at once:
1. Status badge says **`AVAILABLE`** (green) — not `ALL SPOTS FILLED`
   (red).
2. Tag badge says **`9+1`** — not `No +1` (those roles don't help me and
   should never trigger a notification, even if available).
3. Does **not** carry a **`Background Check Required`**-style tag (exact
   wording to be confirmed by inspecting a real page) — I don't want
   those roles regardless of 9+1/availability status.

If any one of those three conditions isn't met, it's not a match — stay
silent.

## The actual pages to watch (starting list)
All on `events.nyrr.org` (this is NYRR's dedicated volunteer-registration
platform, separate from the main nyrr.org marketing site):
- `https://events.nyrr.org/tcs-new-york-city-marathon-start-volunteers`
- `https://events.nyrr.org/race-to-deliver-4m-to-benefit-god-s-love-we-deliver-volunteers`
- `https://events.nyrr.org/nyrr-ted-corbitt-15k-volunteers`
- `https://events.nyrr.org/nyrr-frosty-5k-volunteers`

More race pages will get added to this list over time as new races get
posted throughout the year — the tool needs to make that easy (a simple
config file edit, not a code change).

## Constraints that shape the build
- **Free only.** GitHub Actions' free tier comfortably covers a 30-minute
  cadence — no paid service should be needed anywhere in this build.
- **Respect the site.** Before scraping any page, check its robots.txt at
  runtime and never scrape a disallowed page. If more than 5 of my target
  race pages turn out to be robots-disallowed, the auto-check design
  doesn't scale as a manual-fallback hybrid — stop and flag it rather
  than force it, so we can rethink the approach for those pages
  specifically.
- **Notify only, never act.** The tool should never attempt to log in to
  my NYRR account, store any NYRR credentials, or auto-register me for a
  slot. I want to be the one who clicks through and completes
  registration myself — partly because registering is a fast, simple
  step once I have the link, and partly because I don't want an
  automated system holding my login or payment details.
- **No guessing at page structure.** The site's actual HTML/API structure
  needs to be inspected for real (via the discovery script) before the
  matching logic is written — don't assume a layout and build against
  that assumption.
- **Fail loud, not silent.** If the scraper breaks (NYRR changes their
  page and the parser stops finding what it expects), I want to know via
  a distinct alert — a monitor that silently stops working is worse than
  no monitor.

## What this explicitly does NOT need to do
- Doesn't need to monitor race *registration* (running) availability —
  volunteer roles only.
- Doesn't need to handle the September 8 mass-opening specially — that
  one I'll be ready for manually since I know the exact date/time; this
  tool exists for the unpredictable cancellation-driven reopenings in
  between.
- Doesn't need a web UI/dashboard — a phone push notification is the
  entire interface.

## How this fits together with the other two files
- `SPEC.md` has the full technical architecture: components, data flow,
  state handling, notification rules, the robots.txt decision gate, and
  open questions to resolve during discovery.
- `PROMPTS.md` has the exact, ordered prompts to paste into Claude Code
  to build it — starting with a discovery pass against the real URLs
  above, with an explicit checkpoint before proceeding further.
