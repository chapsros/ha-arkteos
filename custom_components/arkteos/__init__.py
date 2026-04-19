"""Intégration Arkteos V4."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from .protocol import ArkteosProtocol, DEFAULT_PORT
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

DOMAIN = "arkteos"
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    protocol = ArkteosProtocol(host, port)
    await protocol.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = protocol
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        protocol: ArkteosProtocol = hass.data[DOMAIN].pop(entry.entry_id)
        await protocol.stop()
    return unload_ok
