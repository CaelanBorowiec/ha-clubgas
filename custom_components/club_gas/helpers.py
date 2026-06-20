"""Shared helpers for the Club Gas integration."""

from __future__ import annotations

from typing import Any

from .const import CONF_USERS


def get_configured_users(entry: Any) -> list[dict[str, Any]]:
    """Return household driver settings stored in integration options."""
    options = getattr(entry, "options", {})
    if CONF_USERS in options:
        return list(options[CONF_USERS])
    data = getattr(entry, "data", {})
    return list(data.get(CONF_USERS, []))
