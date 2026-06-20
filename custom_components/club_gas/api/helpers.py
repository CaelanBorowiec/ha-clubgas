"""Shared helpers for Club Gas API clients."""

from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse

from ..const import BRAND_COSTCO, BRAND_SAMS, SAMS_FUEL_URL_TEMPLATE

COSTCO_URL_RE = re.compile(
    r"costco\.com/w/-/(?:[^/]+/)?[^/]+/(\d+)",
    re.IGNORECASE,
)
SAMS_URL_RE = re.compile(
    r"samsclub\.com/club/(\d+)(?:-[^/]+)?/fuel-center",
    re.IGNORECASE,
)
SAMS_ID_RE = re.compile(r"^sams[:\s#-]*(\d+)$", re.IGNORECASE)
COSTCO_ID_RE = re.compile(r"^costco[:\s#-]*(\d+)$", re.IGNORECASE)
SAMS_PRICE_TEXT_RE = re.compile(
    r"(Unleaded|Premium)\s+(\d+\.\d+)\s+dollars and \d+ tenths cents",
    re.IGNORECASE,
)
SAMS_NEARBY_RE = re.compile(
    r'href="(/club/\d+-[^"]+/fuel-center)"',
    re.IGNORECASE,
)


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in miles."""
    radius_miles = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_miles * math.asin(math.sqrt(a))


def parse_price(value: Any) -> float | None:
    """Parse a price string or number."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if float(value) > 0 else None
    text = str(value).strip()
    if not text:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def parse_station_reference(value: str) -> tuple[str, str, str | None]:
    """Parse a station URL or bare ID into brand, store_id, optional URL."""
    text = value.strip()
    if not text:
        raise ValueError("Station reference cannot be empty")

    if match := COSTCO_URL_RE.search(text):
        store_id = match.group(1)
        return BRAND_COSTCO, store_id, text if text.startswith("http") else None

    if match := SAMS_URL_RE.search(text):
        store_id = match.group(1)
        url = text if text.startswith("http") else SAMS_FUEL_URL_TEMPLATE.format(club_id=store_id)
        return BRAND_SAMS, store_id, url

    if match := COSTCO_ID_RE.match(text):
        return BRAND_COSTCO, match.group(1), None

    if match := SAMS_ID_RE.match(text):
        store_id = match.group(1)
        return BRAND_SAMS, store_id, SAMS_FUEL_URL_TEMPLATE.format(club_id=store_id)

    if text.isdigit():
        raise ValueError(
            "Numeric store IDs must be prefixed with brand, e.g. costco:332 or sams:6677"
        )

    parsed = urlparse(text)
    if parsed.netloc:
        raise ValueError(f"Unsupported station URL: {text}")

    raise ValueError(f"Could not parse station reference: {text}")


def build_sams_fuel_url(club_id: str) -> str:
    """Build a Sam's Club fuel-center URL from club ID."""
    return SAMS_FUEL_URL_TEMPLATE.format(club_id=club_id)


def parse_sams_prices(html: str) -> dict[str, float | None]:
    """Extract unleaded and premium prices from a Sam's fuel-center page."""
    prices: dict[str, float | None] = {"unleaded": None, "premium": None}
    for fuel_type, price_text in SAMS_PRICE_TEXT_RE.findall(html):
        key = fuel_type.lower()
        prices[key] = parse_price(price_text)
    return prices


def extract_sams_nearby_links(html: str) -> list[str]:
    """Extract nearby fuel-center links from a Sam's page."""
    links: list[str] = []
    seen: set[str] = set()
    for path in SAMS_NEARBY_RE.findall(html):
        if path not in seen:
            seen.add(path)
            links.append(f"https://www.samsclub.com{path}")
    return links
