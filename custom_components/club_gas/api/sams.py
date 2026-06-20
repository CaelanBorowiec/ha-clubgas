"""Sam's Club fuel-center page client."""

from __future__ import annotations

import logging
import re

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from ..const import BRAND_SAMS, USER_AGENT
from ..models import StationConfig, StationData
from .helpers import (
    build_sams_fuel_url,
    extract_sams_nearby_links,
    haversine_miles,
    parse_sams_prices,
    parse_station_reference,
)

_LOGGER = logging.getLogger(__name__)

SAMS_ADDRESS_RE = re.compile(r"(\d+[^,\n]+,\s*[^,\n]+,\s*[A-Z]{2}\s*\d{5})")


class SamsClient:
    """Fetch Sam's Club fuel prices from fuel-center pages."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def discover_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float,
        seed_club_id: str | None = None,
    ) -> list[StationData]:
        """Discover Sam's fuel centers by crawling nearby links from a seed page."""
        seed_id = seed_club_id or "6677"
        seed_url = build_sams_fuel_url(seed_id)
        html = await self._fetch_html(seed_url)
        candidate_urls = [seed_url, *extract_sams_nearby_links(html)]
        stations: list[StationData] = []
        seen: set[str] = set()
        for url in candidate_urls:
            club_id = parse_station_reference(url)[1]
            if club_id in seen:
                continue
            seen.add(club_id)
            try:
                station = await self.fetch_station(url, latitude, longitude)
            except Exception as err:  # noqa: BLE001 - log and continue discovery
                _LOGGER.debug("Skipping Sam's club %s: %s", club_id, err)
                continue
            if station is None:
                continue
            if station.distance_miles is not None and station.distance_miles > radius_miles:
                continue
            stations.append(station)
        stations.sort(key=lambda item: item.distance_miles or 9999)
        return stations

    async def fetch_station(
        self,
        reference: str,
        home_lat: float,
        home_lng: float,
    ) -> StationData | None:
        """Fetch a Sam's Club fuel center by URL or club ID."""
        brand, club_id, url = parse_station_reference(reference)
        if brand != BRAND_SAMS:
            raise ValueError(f"Expected Sam's Club reference, got {brand}")
        page_url = url or build_sams_fuel_url(club_id)
        html = await self._fetch_html(page_url)
        prices = parse_sams_prices(html)
        if not any(price is not None for price in prices.values()):
            return None

        name, address = _parse_page_metadata(html, club_id)
        latitude, longitude = _parse_coordinates(html)
        distance = None
        if latitude is not None and longitude is not None:
            distance = haversine_miles(home_lat, home_lng, latitude, longitude)

        return StationData(
            brand=BRAND_SAMS,
            store_id=club_id,
            name=name,
            address=address,
            latitude=latitude,
            longitude=longitude,
            distance_miles=distance,
            url=page_url,
            prices=prices,
        )

    async def fetch_configured(
        self,
        stations: list[StationConfig],
        home_lat: float,
        home_lng: float,
    ) -> list[StationData]:
        """Fetch all configured Sam's Club stations."""
        results: list[StationData] = []
        for station in stations:
            reference = station.url or build_sams_fuel_url(station.store_id)
            try:
                parsed = await self.fetch_station(reference, home_lat, home_lng)
            except Exception as err:  # noqa: BLE001 - keep other stations updating
                _LOGGER.warning("Failed to fetch Sam's club %s: %s", station.store_id, err)
                continue
            if parsed is None:
                _LOGGER.warning("Sam's club %s has no fuel prices", station.store_id)
                continue
            if station.name:
                parsed.name = station.name
            results.append(parsed)
        return results

    async def _fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        }
        async with self._session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.text()


def _parse_page_metadata(html: str, club_id: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("h1")
    name = title.get_text(" ", strip=True) if title else f"Sam's Club #{club_id}"
    if not name:
        name = f"Sam's Club #{club_id}"

    address = ""
    if match := SAMS_ADDRESS_RE.search(html):
        address = match.group(1)
    return name, address


def _parse_coordinates(html: str) -> tuple[float | None, float | None]:
    """Best-effort coordinate extraction from embedded JSON or meta tags."""
    lat_match = re.search(r'"latitude"\s*:\s*(-?\d+\.\d+)', html)
    lng_match = re.search(r'"longitude"\s*:\s*(-?\d+\.\d+)', html)
    if lat_match and lng_match:
        return float(lat_match.group(1)), float(lng_match.group(1))
    return None, None
