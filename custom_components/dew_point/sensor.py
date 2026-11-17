"""Dew point sensor."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import TemperatureConverter

from . import DewPointConfigEntry
from .const import ATTR_HUMIDITY_ENTITY, ATTR_TEMPERATURE_ENTITY
from .discovery import DewPointSource
from .formula import dew_point


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DewPointConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a dew point sensor for each temperature / humidity pair of the entry."""
    async_add_entities(DewPointSensor(hass, source) for source in entry.runtime_data)


def _as_float(state: State | None) -> float | None:
    """Return the numeric value of a state, None if it has none."""
    if state is None:
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


class DewPointSensor(SensorEntity):
    """Dew point computed from a temperature and a relative humidity sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:thermometer-water"
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, source: DewPointSource) -> None:
        """Initialize the sensor."""
        self._temperature_entity_id = source.temperature_entity_id
        self._humidity_entity_id = source.humidity_entity_id
        self._attr_unique_id = source.unique_id
        self._attr_extra_state_attributes = {
            ATTR_TEMPERATURE_ENTITY: source.temperature_entity_id,
            ATTR_HUMIDITY_ENTITY: source.humidity_entity_id,
        }

        # The device name, if any, is prepended by Home Assistant.
        if source.name is not None:
            self._attr_name = source.name
        elif source.label is None:
            self._attr_translation_key = "dew_point"
        else:
            self._attr_translation_key = "dew_point_labeled"
            self._attr_translation_placeholders = {"label": source.label}

        # Attach the sensor to the device of its sources, without adding this
        # integration's config entry to a device owned by another integration.
        if source.device_id is not None:
            self.device_entry = dr.async_get(hass).async_get(source.device_id)

    async def async_added_to_hass(self) -> None:
        """Compute the first value and follow the source sensors."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._temperature_entity_id, self._humidity_entity_id],
                self._async_source_changed,
            )
        )
        self._async_update_value()

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Rename in place: nothing here depends on this sensor's own entity ID."""
        super().async_entity_id_changed(old_entity_id)

    @callback
    def _async_source_changed(self, _event: Event[EventStateChangedData]) -> None:
        """Recompute when the temperature or the humidity changes."""
        self._async_update_value()
        self.async_write_ha_state()

    @callback
    def _async_update_value(self) -> None:
        """Compute the dew point from the current state of the sources."""
        temperature_state = self.hass.states.get(self._temperature_entity_id)
        humidity_state = self.hass.states.get(self._humidity_entity_id)

        self._attr_available = (
            temperature_state is not None
            and humidity_state is not None
            and STATE_UNAVAILABLE not in (temperature_state.state, humidity_state.state)
        )
        self._attr_native_value = None

        temperature = _as_float(temperature_state)
        humidity = _as_float(humidity_state)
        if temperature is None or humidity is None:
            return

        # Sensor states are expressed in the unit chosen by the user.
        unit = temperature_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if (
            unit in TemperatureConverter.VALID_UNITS
            and unit != UnitOfTemperature.CELSIUS
        ):
            temperature = TemperatureConverter.convert(
                temperature, unit, UnitOfTemperature.CELSIUS
            )

        if (value := dew_point(temperature, humidity)) is not None:
            self._attr_native_value = round(value, 2)
