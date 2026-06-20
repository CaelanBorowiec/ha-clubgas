"""Sensor platform for Club Gas."""

from __future__ import annotations

import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.helpers import resolve_trip_fuel_type
from .const import (
    ATTR_ADDRESS,
    ATTR_BRAND,
    ATTR_DISTANCE_MILES,
    ATTR_FUEL_TYPE,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MPG,
    ATTR_PRICE,
    ATTR_STORE_ID,
    ATTR_STORE_NAME,
    ATTR_TRIP_COST,
    ATTR_TRIP_GALLONS,
    ATTR_USER_ID,
    ATTR_USER_NAME,
    CONF_FUEL_TYPES,
    CONF_STATIONS,
    CONF_USER_FUEL_TYPE,
    CONF_USERS,
    DEFAULT_USER_FUEL_TYPE,
    DOMAIN,
    FUEL_DIESEL,
    FUEL_PREMIUM,
    FUEL_REGULAR,
    FUEL_UNLEADED,
)
from .coordinator import ClubGasCoordinator, get_coordinator
from .models import StationData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Club Gas sensors."""
    coordinator = get_coordinator(hass, entry)
    entities: list[SensorEntity] = []

    fuel_types = set(entry.data.get(CONF_FUEL_TYPES, []))
    users = entry.data.get(CONF_USERS, [])
    station_keys = {
        f"{station['brand']}:{station['store_id']}"
        for station in entry.data.get(CONF_STATIONS, [])
    }

    for station_key in station_keys:
        brand, store_id = station_key.split(":", 1)
        station_name = _station_name(entry, brand, store_id)
        brand_fuels = _brand_fuel_types(brand, fuel_types)
        for fuel_type in brand_fuels:
            entities.append(
                ClubGasPriceSensor(
                    coordinator,
                    entry,
                    brand,
                    store_id,
                    station_name,
                    fuel_type,
                )
            )
        for user in users:
            user_fuel = user.get(CONF_USER_FUEL_TYPE, DEFAULT_USER_FUEL_TYPE)
            trip_fuel = resolve_trip_fuel_type(brand, user_fuel)
            if trip_fuel is None:
                continue
            entities.append(
                ClubGasTripCostSensor(
                    coordinator,
                    entry,
                    brand,
                    store_id,
                    station_name,
                    trip_fuel,
                    user,
                )
            )

    async_add_entities(entities)


def _brand_fuel_types(brand: str, fuel_types: set[str]) -> list[str]:
    if brand == "costco":
        fuels = [fuel for fuel in (FUEL_REGULAR, FUEL_PREMIUM, FUEL_DIESEL) if fuel in fuel_types]
        return fuels or [FUEL_REGULAR, FUEL_PREMIUM, FUEL_DIESEL]
    fuels = [fuel for fuel in (FUEL_UNLEADED, FUEL_PREMIUM) if fuel in fuel_types]
    return fuels or [FUEL_UNLEADED, FUEL_PREMIUM]


def _station_name(entry: ConfigEntry, brand: str, store_id: str) -> str:
    for station in entry.data.get(CONF_STATIONS, []):
        if station["brand"] == brand and str(station["store_id"]) == str(store_id):
            return station.get("name") or f"{brand.title()} #{store_id}"
    return f"{brand.title()} #{store_id}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return slug or "user"


class ClubGasPriceSensor(CoordinatorEntity[ClubGasCoordinator], SensorEntity):
    """Fuel price sensor for a station."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "USD/gal"

    def __init__(
        self,
        coordinator: ClubGasCoordinator,
        entry: ConfigEntry,
        brand: str,
        store_id: str,
        station_name: str,
        fuel_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._brand = brand
        self._store_id = store_id
        self._fuel_type = fuel_type
        self._station_name = station_name
        self._attr_unique_id = f"{entry.entry_id}_{brand}_{store_id}_{fuel_type}_price"
        self._attr_name = fuel_type.replace("_", " ").title()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{brand}_{store_id}")},
            name=station_name,
            manufacturer=brand.title(),
            model="Fuel Center",
        )

    @property
    def available(self) -> bool:
        station = self._get_station()
        return super().available and station is not None

    @property
    def native_value(self) -> float | None:
        station = self._get_station()
        if station is None:
            return None
        return station.prices.get(self._fuel_type)

    @property
    def extra_state_attributes(self) -> dict[str, str | float | None]:
        station = self._get_station()
        if station is None:
            return {}
        return {
            ATTR_BRAND: self._brand,
            ATTR_STORE_ID: self._store_id,
            ATTR_STORE_NAME: station.name,
            ATTR_FUEL_TYPE: self._fuel_type,
            ATTR_ADDRESS: station.address,
            ATTR_LATITUDE: station.latitude,
            ATTR_LONGITUDE: station.longitude,
            ATTR_DISTANCE_MILES: station.distance_miles,
            ATTR_PRICE: station.prices.get(self._fuel_type),
        }

    def _get_station(self) -> StationData | None:
        return self.coordinator.data.get(f"{self._brand}:{self._store_id}")


class ClubGasTripCostSensor(CoordinatorEntity[ClubGasCoordinator], SensorEntity):
    """Trip cost sensor for a user, station, and fuel type."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "USD"

    def __init__(
        self,
        coordinator: ClubGasCoordinator,
        entry: ConfigEntry,
        brand: str,
        store_id: str,
        station_name: str,
        fuel_type: str,
        user: dict,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._brand = brand
        self._store_id = store_id
        self._fuel_type = fuel_type
        self._station_name = station_name
        self._user = user
        user_slug = _slug(user.get("user_name", user["user_id"]))
        fuel_label = self._fuel_type.replace("_", " ").title()
        self._attr_unique_id = (
            f"{entry.entry_id}_{brand}_{store_id}_trip_{user['user_id']}"
        )
        self._attr_name = f"Trip cost ({user.get('user_name', user_slug)}, {fuel_label})"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{brand}_{store_id}")},
            name=station_name,
            manufacturer=brand.title(),
            model="Fuel Center",
        )

    @property
    def available(self) -> bool:
        station = self._get_station()
        price = None if station is None else station.prices.get(self._fuel_type)
        return (
            super().available
            and station is not None
            and price is not None
            and station.distance_miles is not None
            and self._user.get("mpg")
        )

    @property
    def native_value(self) -> float | None:
        trip = self._trip_details()
        if trip is None:
            return None
        return round(trip["trip_cost"], 2)

    @property
    def extra_state_attributes(self) -> dict[str, str | float | None]:
        trip = self._trip_details()
        station = self._get_station()
        if trip is None or station is None:
            return {}
        return {
            ATTR_BRAND: self._brand,
            ATTR_STORE_ID: self._store_id,
            ATTR_STORE_NAME: station.name,
            ATTR_FUEL_TYPE: self._fuel_type,
            ATTR_USER_ID: self._user["user_id"],
            ATTR_USER_NAME: self._user.get("user_name"),
            ATTR_MPG: self._user.get("mpg"),
            ATTR_DISTANCE_MILES: station.distance_miles,
            ATTR_PRICE: station.prices.get(self._fuel_type),
            ATTR_TRIP_GALLONS: round(trip["trip_gallons"], 3),
            ATTR_TRIP_COST: round(trip["trip_cost"], 2),
        }

    def _get_station(self) -> StationData | None:
        return self.coordinator.data.get(f"{self._brand}:{self._store_id}")

    def _trip_details(self) -> dict[str, float] | None:
        station = self._get_station()
        if station is None:
            return None
        price = station.prices.get(self._fuel_type)
        distance = station.distance_miles
        mpg = self._user.get("mpg")
        if price is None or distance is None or not mpg:
            return None
        trip_gallons = distance / float(mpg)
        return {
            "trip_gallons": trip_gallons,
            "trip_cost": trip_gallons * price,
        }
