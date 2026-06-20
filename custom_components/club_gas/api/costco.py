"""Costco US warehouse gas price client."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession

from ..const import BRAND_COSTCO, COSTCO_AJAX_URL, COSTCO_USER_AGENT
from ..models import StationConfig, StationData
from .helpers import haversine_miles, parse_price

_LOGGER = logging.getLogger(__name__)


class CostcoClient:
    """Fetch Costco gas prices via the warehouse locator AJAX endpoint."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def discover_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float,
    ) -> list[StationData]:
        """Return Costco gas stations near a location."""
        warehouses = await self._fetch_warehouses(latitude, longitude)
        stations: list[StationData] = []
        for warehouse in warehouses:
            lat = warehouse.get("latitude")
            lng = warehouse.get("longitude")
            if lat is None or lng is None:
                continue
            distance = haversine_miles(latitude, longitude, float(lat), float(lng))
            if distance > radius_miles:
                continue
            station = self._parse_warehouse(warehouse, distance)
            if station and station.prices:
                stations.append(station)
        stations.sort(key=lambda item: item.distance_miles or 9999)
        return stations

    async def fetch_station(
        self,
        store_id: str,
        home_lat: float,
        home_lng: float,
    ) -> StationData | None:
        """Fetch a specific Costco warehouse by searching near home."""
        warehouses = await self._fetch_warehouses(home_lat, home_lng)
        for warehouse in warehouses:
            if str(warehouse.get("stlocID")) != str(store_id):
                continue
            lat = warehouse.get("latitude")
            lng = warehouse.get("longitude")
            distance = None
            if lat is not None and lng is not None:
                distance = haversine_miles(home_lat, home_lng, float(lat), float(lng))
            return self._parse_warehouse(warehouse, distance)
        return None

    async def fetch_configured(
        self,
        stations: list[StationConfig],
        home_lat: float,
        home_lng: float,
    ) -> list[StationData]:
        """Fetch all configured Costco stations."""
        warehouses = await self._fetch_warehouses(home_lat, home_lng)
        by_id = {str(item.get("stlocID")): item for item in warehouses}
        results: list[StationData] = []
        for station in stations:
            warehouse = by_id.get(str(station.store_id))
            if warehouse is None:
                _LOGGER.warning("Costco warehouse %s not found near home", station.store_id)
                continue
            lat = warehouse.get("latitude")
            lng = warehouse.get("longitude")
            distance = None
            if lat is not None and lng is not None:
                distance = haversine_miles(home_lat, home_lng, float(lat), float(lng))
            parsed = self._parse_warehouse(warehouse, distance)
            if parsed:
                if station.name:
                    parsed.name = station.name
                results.append(parsed)
        return results

    async def _fetch_warehouses(
        self, latitude: float, longitude: float
    ) -> list[dict[str, Any]]:
        params = {
            "numOfWarehouses": "50",
            "hasGas": "true",
            "populateWarehouseDetails": "true",
            "latitude": str(latitude),
            "longitude": str(longitude),
            "countryCode": "US",
        }
        # Minimal headers (see gastrak). Browser UA + Referer triggers Akamai 403.
        headers = {
            "User-Agent": COSTCO_USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
        }
        async with self._session.get(
            COSTCO_AJAX_URL, params=params, headers=headers
        ) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
        if not isinstance(payload, list):
            raise TypeError("Unexpected Costco response format")
        return [item for item in payload[1:] if isinstance(item, dict)]

    def _parse_warehouse(
        self, warehouse: dict[str, Any], distance: float | None
    ) -> StationData | None:
        gas_prices = warehouse.get("gasPrices") or {}
        prices = {
            "regular": parse_price(gas_prices.get("regular")),
            "premium": parse_price(gas_prices.get("premium")),
            "diesel": parse_price(gas_prices.get("diesel")),
        }
        if not any(price is not None for price in prices.values()):
            return None

        address_parts = [
            warehouse.get("address1"),
            warehouse.get("city"),
            warehouse.get("state"),
            warehouse.get("zipCode"),
        ]
        address = ", ".join(part for part in address_parts if part)
        store_id = str(warehouse.get("stlocID", ""))
        return StationData(
            brand=BRAND_COSTCO,
            store_id=store_id,
            name=str(warehouse.get("locationName") or f"Costco #{store_id}"),
            address=address,
            latitude=_maybe_float(warehouse.get("latitude")),
            longitude=_maybe_float(warehouse.get("longitude")),
            distance_miles=distance,
            url=f"https://www.costco.com/w/-/warehouse/{store_id}",
            prices=prices,
        )


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
