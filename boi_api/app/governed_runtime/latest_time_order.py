"""Declared temporal comparison, shared by execution and snapshot page readers."""
from datetime import date, datetime, timedelta
import hashlib
from pathlib import Path
import re
from typing import Literal

TimeOrdering = Literal["ISO8601_UTC", "SOURCE_LOCAL_ISO8601", "ISO_DATE"]


def time_function_digest():
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def time_key(value, policy):
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        if policy == "ISO_DATE":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return None
            return date.fromisoformat(value).isoformat()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)?", value):
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if policy == "ISO8601_UTC":
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                return None
        elif policy == "SOURCE_LOCAL_ISO8601":
            if parsed.tzinfo is not None:
                return None
        else:
            return None
        return parsed.replace(tzinfo=None).isoformat(timespec="microseconds")
    except ValueError:
        return None


def register_latest_time_functions(connection):
    connection.create_function("boi_latest_time_key", 2, time_key, deterministic=True)
