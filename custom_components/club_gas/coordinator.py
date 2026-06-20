"""DataUpdateCoordinator for Club Gas."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.costco import CostcoClient
from .api.sams import SamsClient
from .const import (
    BRAND_COSTCO,
    BRAND_SAMS,
    CONF_HOME_LAT,
    CONF_HOME_LNG,
    CONF_RETAILERS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DOMAIN,
)
from .models import StationConfig, StationData

_LOGGER = logging.getLogger(__name__)


class ClubGasCoordinator(DataUpdateCoordinator[dict[str, StationData]]):
    """Fetch and merge Costco and Sam's Club fuel prices."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        scan_minutes = entry.data.get(CONF_SCAN_INTERVAL, 180)
        self.config_entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_minutes),
        )
        self._session = ClientSession()
        self._costco = CostcoClient(self._session)
        self._sams = SamsClient(self._session)

    async def async_shutdown(self) -> None:
        """Close the HTTP session."""
        await self._session.close()

    async def _async_update_data(self) -> dict[str, StationData]:
        data = self.config_entry.data
        home_lat = float(data[CONF_HOME_LAT])
        home_lng = float(data[CONF_HOME_LNG])
        retailers = set(data.get(CONF_RETAILERS, [BRAND_COSTCO, BRAND_SAMS]))
        stations_cfg = [
            StationConfig(
                brand=item["brand"],
                store_id=str(item["store_id"]),
                name=item.get("name", ""),
                url=item.get("url"),
            )
            for item in data.get(CONF_STATIONS, [])
        ]

        costco_stations = [
            station for station in stations_cfg if station.brand == BRAND_COSTCO
        ]
        sams_stations = [station for station in stations_cfg if station.brand == BRAND_SAMS]

        merged: dict[str, StationData] = {}
        errors: list[str] = []

        if BRAND_COSTCO in retailers and costco_stations:
            try:
                for station in await self._costco.fetch_configured(
                    costco_stations, home_lat, home_lng
                ):
                    merged[_station_key(station)] = station
            except Exception as err:  # noqa: BLE001 - surface as UpdateFailed
                errors.append(f"Costco: {err}")

        if BRAND_SAMS in retailers and sams_stations:
            try:
                for station in await self._sams.fetch_configured(
                    sams_stations, home_lat, home_lng
                ):
                    merged[_station_key(station)] = station
            except Exception as err:  # noqa: BLE001 - surface as UpdateFailed
                errors.append(f"Sam's Club: {err}")

        if errors and not merged:
            raise UpdateFailed("; ".join(errors))
        if errors:
            _LOGGER.warning("Partial Club Gas update failure: %s", "; ".join(errors))
        return merged

    async def discover_stations(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float,
        retailers: list[str],
    ) -> list[StationData]:
        """Discover nearby stations for config flow."""
        discovered: list[StationData] = []
        if BRAND_COSTCO in retailers:
            discovered.extend(
                await self._costco.discover_nearby(latitude, longitude, radius_miles)
            )
        if BRAND_SAMS in retailers:
            discovered.extend(
                await self._sams.discover_nearby(latitude, longitude, radius_miles)
            )
        discovered.sort(key=lambda item: item.distance_miles or 9999)
        return discovered

    async def validate_station_reference(
        self,
        reference: str,
        home_lat: float,
        home_lng: float,
    ) -> StationData:
        """Validate a manual station URL/ID during config."""
        from .api.helpers import parse_station_reference

        brand, store_id, url = parse_station_reference(reference)
        if brand == BRAND_COSTCO:
            station = await self._costco.fetch_station(store_id, home_lat, home_lng)
        else:
            station = await self._sams.fetch_station(
                url or reference, home_lat, home_lng
            )
        if station is None:
            raise UpdateFailed("This location has no fuel station or prices")
        return station


def _station_key(station: StationData) -> str:
    return f"{station.brand}:{station.store_id}"


def get_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> ClubGasCoordinator:
    """Return the coordinator for a config entry."""
    coordinator: ClubGasCoordinator = hass.data[DOMAIN][entry.entry_id]
    return coordinator
