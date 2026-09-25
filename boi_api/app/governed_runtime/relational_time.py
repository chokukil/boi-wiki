"""Exact offset-aware instant comparison for relational time ranges."""
from datetime import datetime,timezone
import re


def instant_key(value):
    if value is None:return None
    if not isinstance(value,str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?',value):
        raise ValueError('RELATIONAL_TIMESTAMP_INVALID')
    try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError('RELATIONAL_TIMESTAMP_INVALID') from None
    if parsed.utcoffset() is None:raise ValueError('RELATIONAL_TIMESTAMP_OFFSET_REQUIRED')
    return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')


def register_relational_time(connection):
    connection.create_function('boi_instant_key',1,instant_key,deterministic=True)
