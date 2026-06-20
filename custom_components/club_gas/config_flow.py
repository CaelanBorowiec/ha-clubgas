"""Config flow for Club Gas."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp import ClientSession
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    UserSelector,
)

from .const import (
    BRAND_COSTCO,
    BRAND_SAMS,
    CONF_FUEL_TYPES,
    CONF_HOME_LAT,
    CONF_HOME_LNG,
    CONF_MPG,
    CONF_RADIUS_MILES,
    CONF_RETAILERS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    CONF_USER_ID,
    CONF_USER_NAME,
    CONF_USERS,
    DEFAULT_MPG,
    DEFAULT_RADIUS_MILES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    FUEL_DIESEL,
    FUEL_PREMIUM,
    FUEL_REGULAR,
    FUEL_UNLEADED,
)
from .api.costco import CostcoClient
from .api.helpers import parse_station_reference
from .api.sams import SamsClient
from .models import StationData

_LOGGER = logging.getLogger(__name__)


def _location_schema(hass: HomeAssistant) -> vol.Schema:
    home = hass.config.as_dict()
    default_lat = home.get(CONF_LATITUDE, 0.0)
    default_lng = home.get(CONF_LONGITUDE, 0.0)
    return vol.Schema(
        {
            vol.Required(CONF_HOME_LAT, default=default_lat): NumberSelector(
                NumberSelectorConfig(min=-90, max=90, step=0.0001, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_HOME_LNG, default=default_lng): NumberSelector(
                NumberSelectorConfig(min=-180, max=180, step=0.0001, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_RADIUS_MILES, default=DEFAULT_RADIUS_MILES): NumberSelector(
                NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_RETAILERS, default=[BRAND_COSTCO, BRAND_SAMS]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=BRAND_COSTCO, label="Costco"),
                        SelectOptionDict(value=BRAND_SAMS, label="Sam's Club"),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_FUEL_TYPES,
                default=[FUEL_REGULAR, FUEL_UNLEADED, FUEL_PREMIUM, FUEL_DIESEL],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=FUEL_REGULAR, label="Costco Regular"),
                        SelectOptionDict(value=FUEL_UNLEADED, label="Sam's Unleaded"),
                        SelectOptionDict(value=FUEL_PREMIUM, label="Premium"),
                        SelectOptionDict(value=FUEL_DIESEL, label="Diesel"),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES): NumberSelector(
                NumberSelectorConfig(min=30, max=1440, step=15, mode=NumberSelectorMode.BOX)
            ),
        }
    )


class ClubGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Club Gas."""

    VERSION = 1

    def __init__(self) -> None:
        self._flow_data: dict[str, Any] = {}
        self._discovered: list[StationData] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Start config flow with home location."""
        return await self.async_step_location()

    async def async_step_location(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure home location and search radius."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._flow_data.update(user_input)
            return await self.async_step_discover()

        return self.async_show_form(
            step_id="location",
            data_schema=_location_schema(self.hass),
            errors=errors,
        )

    async def async_step_discover(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Discover nearby stations or accept manual URLs."""
        errors: dict[str, str] = {}
        if user_input is None:
            async with ClientSession() as session:
                try:
                    self._discovered = await _discover_stations(
                        session,
                        float(self._flow_data[CONF_HOME_LAT]),
                        float(self._flow_data[CONF_HOME_LNG]),
                        float(self._flow_data[CONF_RADIUS_MILES]),
                        list(self._flow_data[CONF_RETAILERS]),
                    )
                except Exception as err:  # noqa: BLE001 - show in UI
                    _LOGGER.exception("Discovery failed")
                    errors["base"] = str(err)

        if user_input is not None:
            selected_keys = set(user_input.get("selected", []))
            manual = (user_input.get("manual_stations") or "").strip()
            stations = [
                _station_to_config(station)
                for station in self._discovered
                if _station_option_key(station) in selected_keys
            ]
            if manual:
                for line in manual.splitlines():
                    reference = line.strip()
                    if not reference:
                        continue
                    try:
                        station = await _validate_manual_station(
                            self.hass,
                            self._flow_data,
                            reference,
                        )
                    except Exception as err:  # noqa: BLE001 - show in UI
                        errors["manual_stations"] = str(err)
                        break
                    stations.append(_station_to_config(station))
                else:
                    if not stations:
                        errors["base"] = "Select at least one station or paste a URL"
                    else:
                        self._flow_data[CONF_STATIONS] = _dedupe_stations(stations)
                        return await self.async_step_users()
            elif stations:
                self._flow_data[CONF_STATIONS] = _dedupe_stations(stations)
                return await self.async_step_users()
            else:
                errors["base"] = "Select at least one station or paste a URL"

        options = [
            SelectOptionDict(
                value=_station_option_key(station),
                label=_station_option_label(station),
            )
            for station in self._discovered
        ]
        default_selected = [option["value"] for option in options]

        schema = vol.Schema(
            {
                vol.Optional("selected", default=default_selected): SelectSelector(
                    SelectSelectorConfig(options=options, multiple=True)
                ),
                vol.Optional("manual_stations", default=""): TextSelector(
                    TextSelectorConfig(multiline=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="discover",
            data_schema=schema,
            errors=errors,
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def async_step_users(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure per-user MPG values."""
        errors: dict[str, str] = {}
        if user_input is not None:
            users: list[dict[str, Any]] = []
            for index in range(3):
                user_id = user_input.get(f"user_{index}")
                if not user_id:
                    continue
                mpg = float(user_input.get(f"mpg_{index}", DEFAULT_MPG))
                user_name = await _lookup_user_name(self.hass, user_id)
                users.append(
                    {
                        CONF_USER_ID: user_id,
                        CONF_USER_NAME: user_name,
                        CONF_MPG: mpg,
                    }
                )
            self._flow_data[CONF_USERS] = users
            return self.async_create_entry(title="Club Gas", data=self._flow_data)

        schema_dict: dict[Any, Any] = {}
        for index in range(3):
            schema_dict[vol.Optional(f"user_{index}")] = UserSelector()
            schema_dict[vol.Optional(f"mpg_{index}", default=DEFAULT_MPG)] = NumberSelector(
                NumberSelectorConfig(min=1, max=100, step=0.1, mode=NumberSelectorMode.BOX)
            )
        return self.async_show_form(
            step_id="users",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClubGasOptionsFlow:
        """Return options flow handler."""
        return ClubGasOptionsFlow(config_entry)


class ClubGasOptionsFlow(config_entries.OptionsFlow):
    """Options flow to add stations and update MPG."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            action = user_input["action"]
            if action == "add_station":
                return await self.async_step_add_station()
            if action == "update_mpg":
                return await self.async_step_update_mpg()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="add_station", label="Add station by URL"),
                                SelectOptionDict(value="update_mpg", label="Update user MPG"),
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_add_station(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Add a station by URL."""
        errors: dict[str, str] = {}
        if user_input is not None:
            reference = user_input["reference"].strip()
            try:
                station = await _validate_manual_station(
                    self.hass, self.config_entry.data, reference
                )
            except Exception as err:  # noqa: BLE001 - show in UI
                errors["reference"] = str(err)
            else:
                stations = list(self.config_entry.data.get(CONF_STATIONS, []))
                stations = _dedupe_stations(stations + [_station_to_config(station)])
                new_data = dict(self.config_entry.data)
                new_data[CONF_STATIONS] = stations
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema(
                {
                    vol.Required("reference"): TextSelector(
                        TextSelectorConfig(multiline=False)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_update_mpg(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Update MPG for configured users."""
        if user_input is not None:
            users: list[dict[str, Any]] = []
            for index, existing in enumerate(self.config_entry.data.get(CONF_USERS, [])):
                mpg = float(user_input.get(f"mpg_{index}", existing.get(CONF_MPG, DEFAULT_MPG)))
                users.append({**existing, CONF_MPG: mpg})
            new_data = dict(self.config_entry.data)
            new_data[CONF_USERS] = users
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema_dict: dict[Any, Any] = {}
        for index, user in enumerate(self.config_entry.data.get(CONF_USERS, [])):
            schema_dict[
                vol.Required(f"mpg_{index}", default=user.get(CONF_MPG, DEFAULT_MPG))
            ] = NumberSelector(
                NumberSelectorConfig(min=1, max=100, step=0.1, mode=NumberSelectorMode.BOX)
            )
        return self.async_show_form(step_id="update_mpg", data_schema=vol.Schema(schema_dict))


async def _discover_stations(
    session: ClientSession,
    latitude: float,
    longitude: float,
    radius_miles: float,
    retailers: list[str],
) -> list[StationData]:
    discovered: list[StationData] = []
    if BRAND_COSTCO in retailers:
        discovered.extend(
            await CostcoClient(session).discover_nearby(latitude, longitude, radius_miles)
        )
    if BRAND_SAMS in retailers:
        discovered.extend(
            await SamsClient(session).discover_nearby(latitude, longitude, radius_miles)
        )
    discovered.sort(key=lambda item: item.distance_miles or 9999)
    return discovered


async def _validate_manual_station(
    hass: HomeAssistant,
    flow_data: dict[str, Any],
    reference: str,
) -> StationData:
    async with ClientSession() as session:
        brand, store_id, url = parse_station_reference(reference)
        home_lat = float(flow_data[CONF_HOME_LAT])
        home_lng = float(flow_data[CONF_HOME_LNG])
        if brand == BRAND_COSTCO:
            station = await CostcoClient(session).fetch_station(store_id, home_lat, home_lng)
        else:
            station = await SamsClient(session).fetch_station(
                url or reference, home_lat, home_lng
            )
        if station is None:
            raise ValueError("This location has no fuel station or prices")
        return station


def _station_option_key(station: StationData) -> str:
    return f"{station.brand}:{station.store_id}"


def _station_option_label(station: StationData) -> str:
    price_bits: list[str] = []
    for fuel_type, price in station.prices.items():
        if price is not None:
            price_bits.append(f"{fuel_type} ${price:.3f}")
    price_text = ", ".join(price_bits) if price_bits else "no prices"
    distance = (
        f"{station.distance_miles:.1f} mi"
        if station.distance_miles is not None
        else "? mi"
    )
    return f"{station.name} — {distance} — {price_text}"


def _station_to_config(station: StationData) -> dict[str, Any]:
    return {
        "brand": station.brand,
        "store_id": station.store_id,
        "name": station.name,
        "url": station.url,
    }


def _dedupe_stations(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for station in stations:
        key = f"{station['brand']}:{station['store_id']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(station)
    return unique


async def _lookup_user_name(hass: HomeAssistant, user_id: str) -> str:
    users = await hass.auth.async_get_users()
    for user in users:
        if user.id == user_id:
            return user.name or user_id
    return user_id
