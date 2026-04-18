"""Entité Climate Arkteos - contrôle de la PAC."""
from __future__ import annotations
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .protocol import ArkteosProtocol

_LOGGER = logging.getLogger(__name__)

# Mapping mode_operation -> HVACMode
MODE_MAP = {
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.AUTO,
    0: HVACMode.OFF,
}
HVAC_TO_MODE = {v: k for k, v in MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ArkteosClimate(protocol, entry)])


class ArkteosClimate(ClimateEntity):
    """Entité Climate pour la PAC Arkteos."""

    _attr_has_entity_name = True
    _attr_name = "Pompe à chaleur"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_min_temp = 15.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, protocol: ArkteosProtocol, entry: ConfigEntry) -> None:
        self._protocol = protocol
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Arkteos Pompe à Chaleur",
            manufacturer="Arkteos",
            model="Zuran 3 / REG3",
        )
        self._target_temp: float | None = None

    async def async_added_to_hass(self) -> None:
        self._protocol.register_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        self._protocol.remove_callback(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._protocol.data.available

    @property
    def current_temperature(self) -> float | None:
        return self._protocol.data.temp_zone1

    @property
    def target_temperature(self) -> float | None:
        if self._target_temp is not None:
            return self._target_temp
        return self._protocol.data.consigne_zone1

    @property
    def hvac_mode(self) -> HVACMode:
        mode = self._protocol.data.mode_operation
        return MODE_MAP.get(mode, HVACMode.OFF)

    async def async_set_temperature(self, **kwargs) -> None:
        """Définit la consigne de température."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._target_temp = temp
        # Encodage de la commande de consigne (little-endian x10)
        raw = int(temp * 10)
        # Trame de commande : à affiner selon les captures de commandes
        # Format probable basé sur le protocole REG3
        cmd = bytes([
            0x55, 0x00,          # header
            0x10, 0xff,          # taille + flags
            0x23, 0x40, 0x03,    # identifiant commande
            0x01,                # type: set_temperature zone1
            raw & 0xff,          # byte low
            (raw >> 8) & 0xff,   # byte high
            0x00, 0x00,
            0xaa                 # footer
        ])
        try:
            if self._protocol._writer:
                self._protocol._writer.write(cmd)
                await self._protocol._writer.drain()
                _LOGGER.debug("Consigne envoyée: %.1f°C", temp)
        except Exception as e:
            _LOGGER.error("Erreur envoi consigne: %s", e)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Change le mode de fonctionnement."""
        mode_num = HVAC_TO_MODE.get(hvac_mode, 0)
        cmd = bytes([
            0x55, 0x00,
            0x10, 0xff,
            0x23, 0x40, 0x03,
            0x02,                # type: set_mode
            mode_num,
            0x00, 0x00, 0x00,
            0xaa
        ])
        try:
            if self._protocol._writer:
                self._protocol._writer.write(cmd)
                await self._protocol._writer.drain()
                _LOGGER.debug("Mode changé: %s", hvac_mode)
        except Exception as e:
            _LOGGER.error("Erreur changement mode: %s", e)
        self.async_write_ha_state()
