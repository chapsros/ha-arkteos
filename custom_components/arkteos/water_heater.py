"""Water Heater V4 - Chauffe-eau avec vraies commandes."""
from __future__ import annotations
import asyncio
import logging
from homeassistant.components.water_heater import (
    WaterHeaterEntity, WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .protocol import ArkteosProtocol

_LOGGER = logging.getLogger(__name__)

OPERATION_ARRET = "Arrêt"
OPERATION_MARCHE = "Marche/Prog"
ATTR_RELANCE_TEMPERATURE = "relance_temperature"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]
    await asyncio.sleep(3)
    async_add_entities([ArkteosWaterHeater(protocol, entry)])


class ArkteosWaterHeater(WaterHeaterEntity):
    _attr_has_entity_name = True
    _attr_name = "Chauffe-Eau"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 30.0
    _attr_max_temp = 70.0
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [OPERATION_ARRET, OPERATION_MARCHE]

    def __init__(self, protocol: ArkteosProtocol, entry: ConfigEntry):
        self._protocol = protocol
        self._attr_unique_id = f"{entry.entry_id}_water_heater"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Arkteos Pompe à Chaleur",
            manufacturer="Arkteos",
            model="Zuran 3 / REG3",
        )

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
        return self._protocol.data.ecs.temp_actuelle

    @property
    def target_temperature(self):
        return self._protocol.data.ecs.temp_consigne

    @property
    def current_operation(self):
        mode = self._protocol.data.ecs.mode
        return OPERATION_ARRET if mode == 0 else OPERATION_MARCHE

    @property
    def extra_state_attributes(self):
        return {
            ATTR_RELANCE_TEMPERATURE: self._protocol.data.ecs.temp_relance,
        }

    async def async_set_temperature(self, **kwargs):
        """Change la consigne ECS (garde la relance actuelle)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        relance = self._protocol.data.ecs.temp_relance or 47.0
        ok = await self._protocol.set_ecs(temp, relance)
        if ok:
            self._protocol.data.ecs.temp_consigne = temp
            self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str):
        """Change le mode ECS."""
        # Pour l'instant on envoie juste la commande avec les valeurs actuelles
        consigne = self._protocol.data.ecs.temp_consigne or 54.0
        relance = self._protocol.data.ecs.temp_relance or 47.0
        ok = await self._protocol.set_ecs(consigne, relance)
        if ok:
            self._protocol.data.ecs.mode = 0 if operation_mode == OPERATION_ARRET else 1
            self.async_write_ha_state()

    async def async_set_relance_temperature(self, temperature: float):
        """Service personnalisé pour changer la température de relance."""
        consigne = self._protocol.data.ecs.temp_consigne or 54.0
        ok = await self._protocol.set_ecs(consigne, temperature)
        if ok:
            self._protocol.data.ecs.temp_relance = temperature
            self.async_write_ha_state()
