"""Climate V2 - Radiateur et Plancher avec auto-découverte."""
from __future__ import annotations
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
from .protocol import (
    ArkteosProtocol, ZoneData,
    MODE_ARRET, MODE_CHAUD, MODE_AUTO, MODE_HORS_GEL, MODE_APPOINT,
)

_LOGGER = logging.getLogger(__name__)

HVAC_MODE_MAP = {
    MODE_ARRET: HVACMode.OFF,
    MODE_CHAUD: HVACMode.HEAT,
    MODE_AUTO: HVACMode.AUTO,
    MODE_HORS_GEL: HVACMode.OFF,
    MODE_APPOINT: HVACMode.HEAT,
}
HVAC_TO_MODE = {
    HVACMode.OFF: MODE_ARRET,
    HVACMode.HEAT: MODE_CHAUD,
    HVACMode.AUTO: MODE_AUTO,
}

# Codes zone pour les commandes
ZONE_RADIATEUR = 0x01
ZONE_PLANCHER = 0x02

# Types de commande
CMD_CONSIGNE = 0x01
CMD_MODE = 0x02


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # On attend un premier cycle de données pour détecter les zones
    import asyncio
    await asyncio.sleep(3)

    data = protocol.data
    if data.radiateur.present:
        _LOGGER.info("Zone radiateur détectée")
        entities.append(ArkteosZoneClimate(
            protocol, entry,
            zone_id=ZONE_RADIATEUR,
            zone_name="Radiateur",
            zone_attr="radiateur",
        ))

    if data.plancher.present:
        _LOGGER.info("Zone plancher détectée")
        entities.append(ArkteosZoneClimate(
            protocol, entry,
            zone_id=ZONE_PLANCHER,
            zone_name="Plancher",
            zone_attr="plancher",
        ))

    # Si aucune zone détectée encore, on crée les deux par défaut
    if not entities:
        _LOGGER.info("Aucune zone détectée, création des deux zones par défaut")
        entities.append(ArkteosZoneClimate(
            protocol, entry, ZONE_RADIATEUR, "Radiateur", "radiateur"
        ))
        entities.append(ArkteosZoneClimate(
            protocol, entry, ZONE_PLANCHER, "Plancher", "plancher"
        ))

    async_add_entities(entities)


class ArkteosZoneClimate(ClimateEntity):
    """Entité climate pour une zone (radiateur ou plancher)."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        protocol: ArkteosProtocol,
        entry: ConfigEntry,
        zone_id: int,
        zone_name: str,
        zone_attr: str,
    ) -> None:
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

    def _zone(self) -> ZoneData:
        return getattr(self._protocol.data, self._zone_attr)

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
        return self._zone().temp_ambiante

    @property
    def target_temperature(self) -> float | None:
        return self._zone().temp_consigne

    @property
    def hvac_mode(self) -> HVACMode:
        mode = self._zone().mode
        return HVAC_MODE_MAP.get(mode, HVACMode.OFF)

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        value = int(temp * 10)
        await self._protocol.send_command(CMD_CONSIGNE, self._zone_id, value)
        self._zone().temp_consigne = temp
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode_num = HVAC_TO_MODE.get(hvac_mode, MODE_ARRET)
        await self._protocol.send_command(CMD_MODE, self._zone_id, mode_num)
        self._zone().mode = mode_num
        self.async_write_ha_state()
