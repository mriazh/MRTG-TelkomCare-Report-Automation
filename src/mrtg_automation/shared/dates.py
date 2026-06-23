from datetime import datetime, date, timedelta
from typing import Union

def parse_input_date(date_str: str) -> datetime:
    """
    Parse an input string from CLI into a datetime object.
    Supports formats like YYYYMMDD, YYYY-MM-DD, DD-MM-YYYY, etc.
    To be fully implemented later.
    """
    try:
        # Simple placeholder implementation
        if len(date_str) == 8 and date_str.isdigit():
            return datetime.strptime(date_str, "%Y%m%d")
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYYMMDD or ISO format.")

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

def to_folder_format(date_obj: Union[datetime, date]) -> str:
    """
    Return YYYYMMDD string format for folder and filenames.
    """
    return date_obj.strftime("%Y%m%d")
