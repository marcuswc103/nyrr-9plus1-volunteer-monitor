"""
Shared robots.txt check for events.nyrr.org, used by both discovery.py
(manual, one-off) and scraper.py (every scheduled run). One source of
truth so the User-Agent and allow/disallow logic can't drift apart
between the two, and so scraper.py can re-check the real robots.txt on
every run instead of trusting a config value that could go stale.
"""

import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlparse

USER_AGENT = (
    "NYRR9Plus1VolunteerMonitor/0.1 "
    "(personal, non-commercial monitoring tool; contact: marcuscalero3@gmail.com)"
)

REQUEST_TIMEOUT_SECONDS = 15


def check_robots_allowed(url: str) -> bool:
    """Check robots.txt for the given URL's origin, fetched fresh every call.

    robotparser's own read() uses urllib's default "Python-urllib/x.y" User-
    Agent, which this site 403s (it's blocking generic script UAs, not
    necessarily disallowing us specifically). We fetch robots.txt ourselves
    with our honest, identifiable User-Agent and feed the text to the
    parser, so a UA-based 403 doesn't get misread as "disallow all".

    Fails closed: any error fetching/parsing robots.txt is treated as
    disallowed for this call, never as "assume it's still fine."
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            raw = resp.read()
        rp.parse(raw.decode("utf-8").splitlines())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False
        elif 400 <= e.code < 500:
            # No robots.txt present at all -> nothing is disallowed.
            return True
        else:
            return False
    except Exception:
        return False
    return rp.can_fetch(USER_AGENT, url)
