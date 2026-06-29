"""Venue geography helpers for 2026 World Cup host nations."""

# FIFA host cities → host nation code (USA / CAN / MEX)
CITY_TO_HOST_COUNTRY = {
    "Los Angeles": "USA",
    "San Francisco": "USA",
    "Seattle": "USA",
    "Dallas": "USA",
    "Houston": "USA",
    "Kansas City": "USA",
    "Atlanta": "USA",
    "Miami": "USA",
    "Boston": "USA",
    "Philadelphia": "USA",
    "NY/NJ": "USA",
    "Mexico City": "MEX",
    "Guadalajara": "MEX",
    "Monterrey": "MEX",
    "Toronto": "CAN",
    "Vancouver": "CAN",
}


def city_to_host_country(city: str) -> str:
    """Map match city to host nation code for home-advantage logic."""
    if not city:
        return ""
    return CITY_TO_HOST_COUNTRY.get(city, city)
