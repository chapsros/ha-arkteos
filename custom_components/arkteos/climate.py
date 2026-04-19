"""Climate V4 - Radiateur et Plancher avec vraies commandes."""
from __future__ import annotations
import asyncio
import logging
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .protocol import ArkteosProtocol, ZONE_RADIATEUR, ZONE_PLANCHER, MODE_ARRET, MODE_MARCHE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]
    await asyncio.sleep(3)
    entities = []
    if protocol.data.radiateur.present or not protocol.data.available:
        entities.append(ArkteosZoneClimate(protocol, entry, ZONE_RADIATEUR, "Radiateur", "radiateur"))
    if protocol.data.plancher.present or not protocol.data.available:
        entities.append(ArkteosZoneClimate(protocol, entry, ZONE_PLANCHER, "Plancher", "plancher"))
    if not entities:
        entities = [
            ArkteosZoneClimate(protocol, entry, ZONE_RADIATEUR, "Radiateur", "radiateur"),
            ArkteosZoneClimate(protocol, entry, ZONE_PLANCHER, "Plancher", "plancher"),
        ]
    async_add_entities(entities)


class ArkteosZoneClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, protocol, entry, zone_id, zone_name, zone_attr):
        self._protocol = protocol
        self._zone_id = zone_id
        self._zone_attr = zone_attr
        self._attr_name = zone_name
        self._attr_unique_id = f"{entry.entry_id}_{zone_attr}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Arkteos Pompe à Chaleur",
            manufacturer="Arkteos",
            model="Zuran 3 / REG3",
        )

    def _zone(self):
        return getattr(self._protocol.data, self._zone_attr)

    async def async_added_to_hass(self):
        self._protocol.register_callback(self._handle_update)

    async def async_will_remove_from_hass(self):
        self._protocol.remove_callback(self._handle_update)

    @callback
    def _handle_update(self):
        self.async_write_ha_state()

    @property
    def available(self):
        return self._protocol.data.available

    @property
    def current_temperature(self):
        return self._zone().temp_ambiante

    @property
    def target_temperature(self):
        return self._zone().temp_consigne

    @property
    def hvac_mode(self):
        mode = self._zone().mode
        if mode == MODE_ARRET:
            return HVACMode.OFF
        return HVACMode.HEAT

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        zone = self._zone()
        mode = MODE_MARCHE if zone.mode != MODE_ARRET else MODE_ARRET
        ok = await self._protocol.set_zone(self._zone_id, mode, temp)
        if ok:
            zone.temp_consigne = temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        zone = self._zone()
        mode = MODE_ARRET if hvac_mode == HVACMode.OFF else MODE_MARCHE
        consigne = zone.temp_consigne or 19.0
        ok = await self._protocol.set_zone(self._zone_id, mode, consigne)
        if ok:
            zone.mode = mode
            self.async_write_ha_state()
