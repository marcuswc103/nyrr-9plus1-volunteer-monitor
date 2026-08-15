"""
Tests for notify.py's payload building — mocked, no real ntfy.sh calls.
"""

from unittest.mock import MagicMock, patch

import pytest

import notify


@pytest.fixture(autouse=True)
def ntfy_topic(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "test-topic")


def _mock_post(status_code=200):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if status_code != 200:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def test_send_opening_alert_payload():
    with patch("notify.requests.post", return_value=_mock_post()) as mock_post:
        ok = notify.send_opening_alert("Frosty 5K", "Bag Check", "https://register.nyrr.org/x")

    assert ok is True
    payload = mock_post.call_args.kwargs["json"]
    assert payload["topic"] == "test-topic"
    assert "Bag Check" in payload["title"]
    assert "Frosty 5K" in payload["title"]
    assert payload["priority"] == 5  # urgent
    assert payload["click"] == "https://register.nyrr.org/x"


def test_send_robots_blocked_reminder_noops_on_empty_list():
    with patch("notify.requests.post") as mock_post:
        result = notify.send_robots_blocked_reminder([])

    assert result is None
    mock_post.assert_not_called()


def test_send_robots_blocked_reminder_lists_all_races():
    races = [
        {"race_name": "Race A", "link": "https://events.nyrr.org/a"},
        {"race_name": "Race B", "link": "https://events.nyrr.org/b"},
    ]
    with patch("notify.requests.post", return_value=_mock_post()) as mock_post:
        notify.send_robots_blocked_reminder(races)

    payload = mock_post.call_args.kwargs["json"]
    assert "Race A" in payload["message"]
    assert "Race B" in payload["message"]
    assert payload["priority"] == 3  # default


def test_send_canary_alert_is_distinct_from_opening_alert():
    with patch("notify.requests.post", return_value=_mock_post()) as mock_post:
        notify.send_canary_alert("Ted Corbitt 15K", "selector not found")

    payload = mock_post.call_args.kwargs["json"]
    assert "MONITOR BROKEN" in payload["title"]
    assert "selector not found" in payload["message"]
    assert payload["priority"] == 4  # high
    assert payload["tags"] != ["rotating_light"]


def test_publish_failure_returns_false_and_does_not_raise():
    with patch("notify.requests.post", return_value=_mock_post(status_code=500)):
        ok = notify.send_opening_alert("Race", "Role", "https://example.com")

    assert ok is False


def test_missing_topic_raises():
    import os

    del os.environ["NTFY_TOPIC"]
    with pytest.raises(RuntimeError):
        notify.send_opening_alert("Race", "Role", "https://example.com")
