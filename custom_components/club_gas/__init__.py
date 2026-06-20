"""The Club Gas integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol

from .const import CONF_USERS, DOMAIN, PLATFORMS, SERVICE_REFRESH
from .coordinator import ClubGasCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Club Gas from YAML is not supported."""

    async def async_handle_refresh(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator: ClubGasCoordinator = hass.data[DOMAIN][entry.entry_id]
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_handle_refresh,
        schema=SERVICE_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Club Gas from a config entry."""
    coordinator = ClubGasCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Move household driver settings from config data to options."""
    if entry.version == 1:
        new_data = dict(entry.data)
        users = new_data.pop(CONF_USERS, [])
        options = dict(entry.options)
        options.setdefault(CONF_USERS, users)
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=options,
            version=2,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ClubGasCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
