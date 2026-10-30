
"""Service functions for searching hospitals."""

from src.database.repository import search_hospitals


def find_hospitals(conn, city=None):
    """Validate search inputs and return matching hospitals."""

    if city is not None and not isinstance(city, str):
        raise TypeError("city must be a string or None.")

    if city is not None:
        city = city.strip() or None

    return search_hospitals(conn, city=city)
