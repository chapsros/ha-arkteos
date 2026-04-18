"""Capteurs de température Arkteos."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .protocol import ArkteosProtocol, ArkteosData


@dataclass
class ArtkteosSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ArkteosData], Optional[float]] = lambda d: None


SENSORS: tuple[ArtkteosSensorDescription, ...] = (
    ArtkteosSensorDescription(
        key="temp_eau_depart",
        name="Température départ circuit",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_eau_depart,
    ),
    ArtkteosSensorDescription(
        key="temp_eau_retour",
        name="Température retour circuit",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_eau_retour,
    ),
    ArtkteosSensorDescription(
        key="temp_exterieure",
        name="Température extérieure",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_exterieure,
    ),
    ArtkteosSensorDescription(
        key="temp_ballon_ecs",
        name="Température ballon ECS",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_ballon_ecs,
    ),
    ArtkteosSensorDescription(
        key="temp_condenseur",
        name="Température condenseur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_condenseur,
    ),
    ArtkteosSensorDescription(
        key="temp_evaporateur",
        name="Température évaporateur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_evaporateur,
    ),
    ArtkteosSensorDescription(
        key="temp_refoulement",
        name="Température refoulement",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_refoulement,
    ),
    ArtkteosSensorDescription(
        key="temp_zone1",
        name="Température zone 1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_zone1,
    ),
    ArtkteosSensorDescription(
        key="temp_zone2",
        name="Température zone 2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_zone2,
    ),
    ArtkteosSensorDescription(
        key="temp_depart_plancher",
        name="Température départ plancher",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_depart_plancher,
    ),
    ArtkteosSensorDescription(
        key="temp_retour_plancher",
        name="Température retour plancher",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temp_retour_plancher,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    protocol: ArkteosProtocol = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ArtkteosSensor(protocol, entry, desc) for desc in SENSORS
    )


class ArtkteosSensor(SensorEntity):
    """Capteur de température Arkteos."""

    _attr_has_entity_name = True

    def __init__(
        self,
        protocol: ArkteosProtocol,
        entry: ConfigEntry,
        description: ArtkteosSensorDescription,
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
        return self._protocol.data.available

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self._protocol.data)
