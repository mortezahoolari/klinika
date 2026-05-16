"""Clock tools — get_current_time and get_current_date."""

from datetime import datetime, timezone, timedelta

# Central European Time (CET/CEST handled manually for simplicity)
_CET = timezone(timedelta(hours=1))
_CEST = timezone(timedelta(hours=2))


def _berlin_now() -> datetime:
    """Current time in Europe/Berlin (simplified: uses CEST Apr-Oct, CET otherwise)."""
    utc_now = datetime.now(timezone.utc)
    month = utc_now.month
    tz = _CEST if 4 <= month <= 10 else _CET
    return utc_now.astimezone(tz)


def get_current_time() -> str:
    """Returns the current time in HH:MM format (Europe/Berlin)."""
    return _berlin_now().strftime("%H:%M")


def get_current_date() -> str:
    """Returns the current date in YYYY-MM-DD format (Europe/Berlin)."""
    return _berlin_now().strftime("%Y-%m-%d")


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Returns the current time in HH:MM format (Europe/Berlin timezone).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": get_current_time,
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Returns the current date in YYYY-MM-DD format (Europe/Berlin timezone).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": get_current_date,
    },
]
