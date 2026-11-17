"""Tests for the dew point sensors."""

from datetime import timedelta

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.dew_point import formula
from custom_components.dew_point.const import (
    CONF_HUMIDITY_ENTITY,
    CONF_MODE,
    CONF_TEMPERATURE_ENTITY,
    DOMAIN,
    MODE_MANUAL,
    RESCAN_DELAY,
)

from . import add_device, add_sensor, setup_auto


def dew_point(temperature: float, humidity: float):  # noqa: ANN201
    """Return the value a sensor must show (the formula has its own tests)."""
    return pytest.approx(round(formula.dew_point(temperature, humidity), 2))


async def rescan(hass: HomeAssistant) -> None:
    """Let the delayed scan that follows entity registry changes run."""
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RESCAN_DELAY + 1)
    )
    await hass.async_block_till_done()


def dew_point_entities(
    hass: HomeAssistant, entry: MockConfigEntry
) -> list[er.RegistryEntry]:
    """Return the entities created by a config entry."""
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def setup_manual(
    hass: HomeAssistant, temperature: str, humidity: str
) -> MockConfigEntry:
    """Set up a manual pair."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cellar dew point",
        data={
            CONF_MODE: MODE_MANUAL,
            CONF_TEMPERATURE_ENTITY: temperature,
            CONF_HUMIDITY_ENTITY: humidity,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensor_added_to_device(hass: HomeAssistant) -> None:
    """The automatic mode attaches a dew point sensor to the device."""
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature", state="20")
    humidity = add_sensor(hass, device, "humidity", "humidity", state="50")

    entry = await setup_auto(hass)

    (registry_entry,) = dew_point_entities(hass, entry)
    assert registry_entry.entity_id == "sensor.living_room_dew_point"
    assert registry_entry.device_id == device.id

    state = hass.states.get(registry_entry.entity_id)
    assert float(state.state) == dew_point(20, 50)
    assert state.name == "Living room Dew point"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["temperature_entity"] == temperature.entity_id
    assert state.attributes["humidity_entity"] == humidity.entity_id

    # The device stays owned by its integration: no device belongs to this one.
    assert dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id) == []


async def test_french_name(hass: HomeAssistant) -> None:
    """The sensor is named in the language of Home Assistant."""
    hass.config.language = "fr"
    device = add_device(hass, "Salon")
    add_sensor(hass, device, "temperature", "temperature", state="20")
    add_sensor(hass, device, "humidity", "humidity", state="50")

    entry = await setup_auto(hass)

    (registry_entry,) = dew_point_entities(hass, entry)
    assert hass.states.get(registry_entry.entity_id).name == "Salon Point de rosée"


async def test_value_follows_sources(hass: HomeAssistant) -> None:
    """The dew point is recomputed on each temperature or humidity change."""
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature", state="20")
    humidity = add_sensor(hass, device, "humidity", "humidity", state="50")
    await setup_auto(hass)
    entity_id = "sensor.living_room_dew_point"

    hass.states.async_set(humidity.entity_id, "60", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == dew_point(20, 60)

    hass.states.async_set(temperature.entity_id, "25", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == dew_point(25, 60)

    hass.states.async_set(temperature.entity_id, "unknown")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unknown"

    hass.states.async_set(temperature.entity_id, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"

    hass.states.async_set(temperature.entity_id, "25", {"unit_of_measurement": "°C"})
    hass.states.async_set(humidity.entity_id, "0", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unknown"


async def test_sources_without_state_yet(hass: HomeAssistant) -> None:
    """The sensor waits for its sources, e.g. while Home Assistant starts."""
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature")
    humidity = add_sensor(hass, device, "humidity", "humidity")
    await setup_auto(hass)
    entity_id = "sensor.living_room_dew_point"
    assert hass.states.get(entity_id).state == "unavailable"

    hass.states.async_set(temperature.entity_id, "20", {"unit_of_measurement": "°C"})
    hass.states.async_set(humidity.entity_id, "50", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()

    assert float(hass.states.get(entity_id).state) == dew_point(20, 50)


@pytest.mark.parametrize(("value", "unit"), [("68", "°F"), ("293.15", "K")])
async def test_temperature_unit(hass: HomeAssistant, value: str, unit: str) -> None:
    """Sources in °F or K are converted before the calculation."""
    device = add_device(hass, "Living room")
    add_sensor(hass, device, "temperature", "temperature", state=value, unit=unit)
    add_sensor(hass, device, "humidity", "humidity", state="50")

    await setup_auto(hass)

    state = hass.states.get("sensor.living_room_dew_point")
    assert float(state.state) == dew_point(20, 50)
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_labeled_sensors(hass: HomeAssistant) -> None:
    """A device with two pairs gets two distinct sensors."""
    device = add_device(hass, "Station")
    add_sensor(hass, device, "indoor_temperature", "temperature", state="21")
    add_sensor(hass, device, "indoor_humidity", "humidity", state="45")
    add_sensor(hass, device, "outdoor_temperature", "temperature", state="5")
    add_sensor(hass, device, "outdoor_humidity", "humidity", state="90")

    entry = await setup_auto(hass)

    names = {
        hass.states.get(registry_entry.entity_id).name
        for registry_entry in dew_point_entities(hass, entry)
    }
    assert names == {"Station Dew point Indoor", "Station Dew point Outdoor"}
    indoor = float(hass.states.get("sensor.station_dew_point_indoor").state)
    outdoor = float(hass.states.get("sensor.station_dew_point_outdoor").state)
    assert indoor == dew_point(21, 45)
    assert outdoor == dew_point(5, 90)


async def test_device_added_later(hass: HomeAssistant) -> None:
    """Devices added after the setup get their sensor without a restart."""
    entry = await setup_auto(hass)
    assert dew_point_entities(hass, entry) == []

    device = add_device(hass, "Bathroom")
    add_sensor(hass, device, "temperature", "temperature", state="24")
    add_sensor(hass, device, "humidity", "humidity", state="80")
    await rescan(hass)

    (registry_entry,) = dew_point_entities(hass, entry)
    assert registry_entry.device_id == device.id
    state = hass.states.get("sensor.bathroom_dew_point")
    assert float(state.state) == dew_point(24, 80)


async def test_sensor_removed_with_its_sources(hass: HomeAssistant) -> None:
    """The dew point sensor goes away when a source is removed or disabled."""
    registry = er.async_get(hass)
    kept = add_device(hass, "Kept")
    add_sensor(hass, kept, "temperature", "temperature", state="20")
    add_sensor(hass, kept, "humidity", "humidity", state="50")
    removed = add_device(hass, "Removed")
    add_sensor(hass, removed, "temperature", "temperature", state="20")
    humidity = add_sensor(hass, removed, "humidity", "humidity", state="50")
    entry = await setup_auto(hass)
    assert len(dew_point_entities(hass, entry)) == 2

    registry.async_remove(humidity.entity_id)
    await rescan(hass)

    (registry_entry,) = dew_point_entities(hass, entry)
    assert registry_entry.device_id == kept.id
    assert hass.states.get("sensor.removed_dew_point") is None
    assert float(hass.states.get("sensor.kept_dew_point").state) == dew_point(20, 50)


async def test_disabled_sensor_stays_disabled(hass: HomeAssistant) -> None:
    """Disabling a dew point sensor in the UI is how a device is opted out."""
    registry = er.async_get(hass)
    device = add_device(hass, "Living room")
    add_sensor(hass, device, "temperature", "temperature", state="20")
    add_sensor(hass, device, "humidity", "humidity", state="50")
    entry = await setup_auto(hass)
    (before,) = dew_point_entities(hass, entry)

    registry.async_update_entity(
        before.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    # Home Assistant reloads the config entry 30 s after an entity is disabled.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    (after,) = dew_point_entities(hass, entry)
    assert after.id == before.id
    assert after.disabled_by is er.RegistryEntryDisabler.USER
    assert hass.states.get(before.entity_id) is None


async def test_source_renamed(hass: HomeAssistant) -> None:
    """Renaming a source entity keeps the same dew point sensor working."""
    registry = er.async_get(hass)
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature", state="20")
    add_sensor(hass, device, "humidity", "humidity", state="50")
    entry = await setup_auto(hass)
    (before,) = dew_point_entities(hass, entry)

    registry.async_update_entity(temperature.entity_id, new_entity_id="sensor.salon_t")
    hass.states.async_remove(temperature.entity_id)
    hass.states.async_set("sensor.salon_t", "25", {"unit_of_measurement": "°C"})
    await rescan(hass)

    (after,) = dew_point_entities(hass, entry)
    assert after.id == before.id
    state = hass.states.get(after.entity_id)
    assert state.attributes["temperature_entity"] == "sensor.salon_t"
    assert float(state.state) == dew_point(25, 50)


async def test_unrelated_changes_do_not_reload(hass: HomeAssistant) -> None:
    """Registry changes which keep the same pairs leave the sensors untouched."""
    device = add_device(hass, "Living room")
    add_sensor(hass, device, "temperature", "temperature", state="20")
    add_sensor(hass, device, "humidity", "humidity", state="50")
    await setup_auto(hass)
    first = hass.states.get("sensor.living_room_dew_point")

    add_sensor(hass, device, "battery", "battery", state="80", unit="%")
    add_sensor(hass, add_device(hass, "Plug"), "power", "power", state="3", unit="W")
    await rescan(hass)

    assert hass.states.get("sensor.living_room_dew_point") is first


async def test_manual_pair(hass: HomeAssistant) -> None:
    """A manual pair works with sensors of different devices, or of none."""
    hass.states.async_set("sensor.cellar_t", "12", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.cellar_h", "85", {"unit_of_measurement": "%"})

    entry = await setup_manual(hass, "sensor.cellar_t", "sensor.cellar_h")

    (registry_entry,) = dew_point_entities(hass, entry)
    assert registry_entry.entity_id == "sensor.cellar_dew_point"
    assert registry_entry.device_id is None
    state = hass.states.get("sensor.cellar_dew_point")
    assert state.name == "Cellar dew point"
    assert float(state.state) == dew_point(12, 85)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.cellar_dew_point").state == "unavailable"


async def test_manual_pair_on_one_device(hass: HomeAssistant) -> None:
    """A manual pair taken from a single device is attached to that device."""
    device = add_device(hass, "Probes")
    first = add_sensor(hass, device, "probe_a", "temperature", state="20")
    add_sensor(hass, device, "probe_b", "temperature", state="30")
    humidity = add_sensor(hass, device, "humidity", "humidity", state="50")

    entry = await setup_manual(hass, first.entity_id, humidity.entity_id)

    (registry_entry,) = dew_point_entities(hass, entry)
    assert registry_entry.device_id == device.id
    assert hass.states.get(registry_entry.entity_id).name == "Probes Cellar dew point"


async def test_manual_pair_follows_renames(hass: HomeAssistant) -> None:
    """Renaming a source of a manual pair updates the config entry."""
    temperature = add_sensor(hass, None, "temperature", "temperature", state="12")
    humidity = add_sensor(hass, None, "humidity", "humidity", state="85")
    entry = await setup_manual(hass, temperature.entity_id, humidity.entity_id)

    er.async_get(hass).async_update_entity(
        humidity.entity_id, new_entity_id="sensor.cellar_h"
    )
    hass.states.async_remove(humidity.entity_id)
    hass.states.async_set("sensor.cellar_h", "50", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()

    assert entry.data[CONF_HUMIDITY_ENTITY] == "sensor.cellar_h"
    assert entry.data[CONF_TEMPERATURE_ENTITY] == temperature.entity_id
    state = hass.states.get("sensor.cellar_dew_point")
    assert float(state.state) == dew_point(12, 50)


async def test_manual_pair_not_duplicated_by_auto(hass: HomeAssistant) -> None:
    """The automatic mode skips a pair which was already set up manually."""
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature", state="20")
    humidity = add_sensor(hass, device, "humidity", "humidity", state="50")
    await setup_manual(hass, temperature.entity_id, humidity.entity_id)

    entry = await setup_auto(hass)

    assert dew_point_entities(hass, entry) == []
