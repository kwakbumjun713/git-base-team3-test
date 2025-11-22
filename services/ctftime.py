import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from flask import current_app

_CACHE: Dict[str, Any] = {"timestamp": 0, "events": [], "by_id": {}}


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _format_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    start = _parse_dt(raw.get("start"))
    finish = _parse_dt(raw.get("finish"))
    duration = raw.get("duration") or {}

    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "description": raw.get("description"),
        "format": raw.get("format"),
        "onsite": raw.get("onsite"),
        "weight": raw.get("weight"),
        "location": raw.get("location"),
        "participants": raw.get("participants"),
        "ctftime_url": raw.get("ctftime_url"),
        "url": raw.get("url"),
        "logo": raw.get("logo"),
        "start": start,
        "finish": finish,
        "start_display": start.strftime("%Y-%m-%d %H:%M UTC") if start else "TBD",
        "finish_display": finish.strftime("%Y-%m-%d %H:%M UTC") if finish else "TBD",
        "duration_days": duration.get("days"),
        "duration_hours": duration.get("hours"),
        "description_short": (raw.get("description") or "")[:200],
    }


def fetch_ctftime_events(limit: int = 25) -> List[Dict[str, Any]]:
    now = time.time()
    cache_seconds = current_app.config.get("CTFTIME_CACHE_SECONDS", 600)
    if _CACHE["events"] and now - _CACHE["timestamp"] < cache_seconds:
        return _CACHE["events"]

    api_url = current_app.config.get(
        "CTFTIME_API_URL", "https://ctftime.org/api/v1/events/"
    )
    lookahead = current_app.config.get("CTFTIME_LOOKAHEAD_SECONDS", 60 * 60 * 24 * 90)
    timeout = current_app.config.get("CTFTIME_TIMEOUT", 10)
    params = {
        "limit": limit,
        "start": int(now),
        "finish": int(now + lookahead),
    }

    headers = {
        "User-Agent": current_app.config.get(
            "CTFTIME_USER_AGENT", "HSpaceCatalog/1.0 (+https://example.com)"
        )
    }

    try:
        response = requests.get(api_url, params=params, timeout=timeout, headers=headers)
        response.raise_for_status()
        raw_events = response.json()
    except Exception as exc:  # pragma: no cover - best effort logging
        current_app.logger.warning("CTFtime fetch failed: %s", exc)
        raw_events = []

    events = [_format_event(event) for event in raw_events]
    _CACHE["by_id"] = {event["id"]: event for event in events if event.get("id")}
    _CACHE["timestamp"] = now
    _CACHE["events"] = events
    return events


def get_ctftime_event(event_id: int) -> Optional[Dict[str, Any]]:
    cached = _CACHE.get("by_id") or {}
    event = cached.get(event_id)
    if event:
        return event
    events = fetch_ctftime_events(limit=100)
    return _CACHE["by_id"].get(event_id)
