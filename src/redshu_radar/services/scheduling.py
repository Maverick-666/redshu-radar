from datetime import datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = ZoneInfo("Asia/Shanghai")


def daily_anchor_due(
    last_success: datetime | None,
    now: datetime,
    *,
    timezone: tzinfo = DEFAULT_TIMEZONE,
) -> bool:
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    local_now = now.astimezone(timezone)
    anchor = local_now.replace(hour=0, minute=2, second=0, microsecond=0)
    if local_now < anchor:
        anchor -= timedelta(days=1)
    if last_success is None:
        return True
    if last_success.tzinfo is None:
        raise ValueError("last_success must include a timezone")
    return last_success < anchor
