"""Water Heater V2 - Chauffe-eau Arkteos avec auto-découverte."""
from __future__ import annotations
import logging
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_OFF,
    STATE_ON,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .protocol import ArkteosProtocol, MODE_ECS_MARCHE, MODE_ECS_APPOINT, MODE_ARRET

_LOGGER = logging.getLogger(__name__)

OPERATION_ARRET = "Arrêt"
OPERATION_MARCHE = "Marche/Prog"
OPERATION_APPOINT = "Appoint ECS"

CMD_ECS_CONSIGNE = 0x11
CMD_ECS_RELANCE = 0x12
CMD_ECS_MODE = 0x13
ZONE_ECS = 0x03


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]

    import asyncio
    await asyncio.sleep(3)

    if protocol.data.ecs.present:
        _LOGGER.info("Chauffe-eau ECS détecté")
        async_add_entities([ArkteosWaterHeater(protocol, entry)])
    else:
        # Créer quand même, ça apparaîtra indisponible si pas de ECS
        _LOGGER.info("Chauffe-eau non détecté, création par défaut")
        async_add_entities([ArkteosWaterHeater(protocol, entry)])


class ArkteosWaterHeater(WaterHeaterEntity):
    """Entité chauffe-eau Arkteos."""

    _attr_has_entity_name = True
    _attr_name = "Chauffe-Eau"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 30.0
    _attr_max_temp = 70.0
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [OPERATION_ARRET, OPERATION_MARCHE, OPERATION_APPOINT]

    def __init__(self, protocol: ArkteosProtocol, entry: ConfigEntry) -> None:
        self._protocol = protocol
        self._attr_unique_id = f"{entry.entry_id}_water_heater"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Arkteos Pompe à Chaleur",
            manufacturer="Arkteos",
            model="Zuran 3 / REG3",
        )

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
        return self._protocol.data.ecs.temp_actuelle

    @property
    def target_temperature(self) -> float | None:
        return self._protocol.data.ecs.temp_consigne

    @property
    def current_operation(self) -> str:
        mode = self._protocol.data.ecs.mode
        if mode == MODE_ARRET:
            return OPERATION_ARRET
        if mode == MODE_ECS_APPOINT:
            return OPERATION_APPOINT
        return OPERATION_MARCHE

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        value = int(temp * 10)
        await self._protocol.send_command(CMD_ECS_CONSIGNE, ZONE_ECS, value)
        self._protocol.data.ecs.temp_consigne = temp
        self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        mode_map = {
            OPERATION_ARRET: MODE_ARRET,
            OPERATION_MARCHE: MODE_ECS_MARCHE,
            OPERATION_APPOINT: MODE_ECS_APPOINT,
        }
        mode_num = mode_map.get(operation_mode, MODE_ARRET)
        await self._protocol.send_command(CMD_ECS_MODE, ZONE_ECS, mode_num)
        self._protocol.data.ecs.mode = mode_num
        self.async_write_ha_state()
