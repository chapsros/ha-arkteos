"""Sensors V2 - Capteurs Arkteos avec auto-découverte."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature, UnitOfPressure, PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .protocol import ArkteosProtocol, ArkteosData


@dataclass
class ArtkteosSensorDesc(SensorEntityDescription):
    value_fn: Callable[[ArkteosData], Optional[float]] = lambda d: None
    condition_fn: Callable[[ArkteosData], bool] = lambda d: True


# Capteurs toujours présents
BASE_SENSORS: tuple[ArtkteosSensorDesc, ...] = (
    ArtkteosSensorDesc(
        key="temp_exterieure",
        name="Température extérieure",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_exterieure,
    ),
    ArtkteosSensorDesc(
        key="temp_retour_circuit",
        name="Température retour circuit",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_retour_circuit,
    ),
    ArtkteosSensorDesc(
        key="pression",
        name="Pression circuit",
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.pression,
    ),
    ArtkteosSensorDesc(
        key="temp_condenseur",
        name="Température condenseur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_condenseur,
    ),
    ArtkteosSensorDesc(
        key="temp_evaporateur",
        name="Température évaporateur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_evaporateur,
    ),
    ArtkteosSensorDesc(
        key="temp_refoulement",
        name="Température refoulement",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_refoulement,
    ),
)

# Capteurs zone radiateur (si détecté)
RADIATEUR_SENSORS: tuple[ArtkteosSensorDesc, ...] = (
    ArtkteosSensorDesc(
        key="radiateur_temp_ambiante",
        name="Radiateur - Température ambiante",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.radiateur.temp_ambiante,
        condition_fn=lambda d: d.radiateur.present,
    ),
    ArtkteosSensorDesc(
        key="radiateur_consigne",
        name="Radiateur - Consigne",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.radiateur.temp_consigne,
        condition_fn=lambda d: d.radiateur.present,
    ),
)

# Capteurs zone plancher (si détecté)
PLANCHER_SENSORS: tuple[ArtkteosSensorDesc, ...] = (
    ArtkteosSensorDesc(
        key="plancher_temp_ambiante",
        name="Plancher - Température ambiante",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.plancher.temp_ambiante,
        condition_fn=lambda d: d.plancher.present,
    ),
    ArtkteosSensorDesc(
        key="plancher_consigne",
        name="Plancher - Consigne",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.plancher.temp_consigne,
        condition_fn=lambda d: d.plancher.present,
    ),
    ArtkteosSensorDesc(
        key="plancher_depart",
        name="Plancher - Température départ",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.depart_plancher,
        condition_fn=lambda d: d.plancher.present,
    ),
    ArtkteosSensorDesc(
        key="plancher_retour",
        name="Plancher - Température retour",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.retour_plancher,
        condition_fn=lambda d: d.plancher.present,
    ),
)

# Capteurs ECS (si détecté)
ECS_SENSORS: tuple[ArtkteosSensorDesc, ...] = (
    ArtkteosSensorDesc(
        key="ecs_temp",
        name="Chauffe-eau - Température",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.ecs.temp_actuelle,
        condition_fn=lambda d: d.ecs.present,
    ),
    ArtkteosSensorDesc(
        key="ecs_consigne",
        name="Chauffe-eau - Consigne",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.ecs.temp_consigne,
        condition_fn=lambda d: d.ecs.present,
    ),
    ArtkteosSensorDesc(
        key="ecs_relance",
        name="Chauffe-eau - Température relance",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.ecs.temp_relance,
        condition_fn=lambda d: d.ecs.present,
    ),
)

ALL_SENSORS = BASE_SENSORS + RADIATEUR_SENSORS + PLANCHER_SENSORS + ECS_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]
    # On crée tous les capteurs, ils se masquent si la zone n'est pas présente
    async_add_entities(
        ArtkteosSensor(protocol, entry, desc) for desc in ALL_SENSORS
    )


class ArtkteosSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        protocol: ArkteosProtocol,
        entry: ConfigEntry,
        description: ArtkteosSensorDesc,
    ) -> None:
        self.entity_description = description
        self._protocol = protocol
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
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
        return (
            self._protocol.data.available
            and self.entity_description.condition_fn(self._protocol.data)
        )

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self._protocol.data)
