"""Intégration Arkteos Heat Pump pour Home Assistant."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .protocol import ArkteosProtocol, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

DOMAIN = "arkteos"
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure l'intégration Arkteos."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    protocol = ArkteosProtocol(host, port)
    await protocol.start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = protocol

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge l'intégration Arkteos."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        protocol: ArkteosProtocol = hass.data[DOMAIN].pop(entry.entry_id)
        await protocol.stop()
    return unload_ok
