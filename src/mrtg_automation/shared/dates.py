from datetime import date, datetime, timedelta
from typing import Union


def generate_date_range(start_date: Union[datetime, date], end_date: Union[datetime, date]) -> list[date]:
    """
    Generate a list of date objects between start_date and end_date (inclusive).
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) cannot be before start_date ({start_date})")

    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]
