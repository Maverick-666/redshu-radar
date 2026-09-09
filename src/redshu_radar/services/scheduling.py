from datetime import datetime, timedelta


def daily_anchor_due(last_success: datetime | None, now: datetime) -> bool:
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    anchor = now.replace(hour=0, minute=2, second=0, microsecond=0)
    if now < anchor:
        anchor -= timedelta(days=1)
    if last_success is None:
        return True
    if last_success.tzinfo is None:
        raise ValueError("last_success must include a timezone")
    return last_success < anchor
