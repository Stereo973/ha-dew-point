"""Tests for the detection of temperature / humidity pairs on devices."""

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.dew_point.discovery import async_discover_sources

from . import add_device, add_sensor


async def test_simple_device(hass: HomeAssistant) -> None:
    """A device with one sensor of each kind gets one source."""
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature")
    humidity = add_sensor(hass, device, "humidity", "humidity")
    add_sensor(hass, device, "battery", "battery")

    (source,) = async_discover_sources(hass)

    assert source.temperature_entity_id == temperature.entity_id
    assert source.humidity_entity_id == humidity.entity_id
    assert source.device_id == device.id
    assert source.unique_id == f"{temperature.id}_{humidity.id}"
    assert source.name is None
    assert source.label is None


async def test_incomplete_devices(hass: HomeAssistant) -> None:
    """Devices missing a measurement, and sensors without device, are ignored."""
    add_sensor(hass, add_device(hass, "Thermometer"), "temperature", "temperature")
    add_sensor(hass, add_device(hass, "Hygrometer"), "humidity", "humidity")
    add_sensor(hass, None, "temperature", "temperature")
    add_sensor(hass, None, "humidity", "humidity")

    assert async_discover_sources(hass) == ()


async def test_pairs_do_not_cross_devices(hass: HomeAssistant) -> None:
    """Each device is paired on its own."""
    for name in ("Bedroom", "Kitchen", "Cellar"):
        device = add_device(hass, name)
        add_sensor(hass, device, "temperature", "temperature")
        add_sensor(hass, device, "humidity", "humidity")

    sources = async_discover_sources(hass)

    assert len(sources) == 3
    registry = er.async_get(hass)
    for source in sources:
        temperature = registry.async_get(source.temperature_entity_id)
        humidity = registry.async_get(source.humidity_entity_id)
        assert temperature.device_id == humidity.device_id == source.device_id


async def test_diagnostic_and_disabled_sensors(hass: HomeAssistant) -> None:
    """Diagnostic temperatures do not count, disabled sensors neither."""
    device = add_device(hass, "ESP")
    temperature = add_sensor(hass, device, "temperature", "temperature")
    add_sensor(
        hass,
        device,
        "chip_temperature",
        "temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    add_sensor(hass, device, "humidity", "humidity")

    (source,) = async_discover_sources(hass)
    assert source.temperature_entity_id == temperature.entity_id

    other = add_device(hass, "Other")
    add_sensor(hass, other, "temperature", "temperature")
    add_sensor(
        hass,
        other,
        "humidity",
        "humidity",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    assert async_discover_sources(hass) == (source,)


async def test_indoor_outdoor_station(hass: HomeAssistant) -> None:
    """Several pairs on one device are matched by name and labeled."""
    device = add_device(hass, "Station")
    indoor_t = add_sensor(hass, device, "indoor_temperature", "temperature")
    indoor_h = add_sensor(hass, device, "indoor_humidity", "humidity")
    outdoor_t = add_sensor(hass, device, "outdoor_temperature", "temperature")
    outdoor_h = add_sensor(hass, device, "outdoor_humidity", "humidity")

    sources = {source.label: source for source in async_discover_sources(hass)}

    assert set(sources) == {"Indoor", "Outdoor"}
    assert sources["Indoor"].temperature_entity_id == indoor_t.entity_id
    assert sources["Indoor"].humidity_entity_id == indoor_h.entity_id
    assert sources["Outdoor"].temperature_entity_id == outdoor_t.entity_id
    assert sources["Outdoor"].humidity_entity_id == outdoor_h.entity_id


async def test_extra_temperature_sensor(hass: HomeAssistant) -> None:
    """A derived temperature does not prevent pairing the real one."""
    device = add_device(hass, "Thermostat")
    temperature = add_sensor(hass, device, "temperature", "temperature")
    add_sensor(hass, device, "feels_like_temperature", "temperature")
    add_sensor(hass, device, "floor_temperature", "temperature")
    humidity = add_sensor(hass, device, "humidity", "humidity")

    (source,) = async_discover_sources(hass)

    assert source.temperature_entity_id == temperature.entity_id
    assert source.humidity_entity_id == humidity.entity_id
    assert source.label is None


async def test_french_names(hass: HomeAssistant) -> None:
    """Names are compared without accents, in the language of the entities."""
    device = add_device(hass, "Station météo")
    add_sensor(
        hass, device, "t_int", "temperature", original_name="Température intérieure"
    )
    add_sensor(hass, device, "h_int", "humidity", original_name="Humidité intérieure")
    add_sensor(
        hass, device, "t_ext", "temperature", original_name="Température extérieure"
    )
    add_sensor(hass, device, "h_ext", "humidity", original_name="Humidité extérieure")

    labels = {source.label for source in async_discover_sources(hass)}

    assert labels == {"intérieure", "extérieure"}


async def test_ambiguous_device(hass: HomeAssistant) -> None:
    """When names do not tell which temperature goes with the humidity: no pair."""
    device = add_device(hass, "Probes")
    add_sensor(hass, device, "probe_a", "temperature")
    add_sensor(hass, device, "probe_b", "temperature")
    add_sensor(hass, device, "humidity", "humidity")

    assert async_discover_sources(hass) == ()


async def test_device_with_its_own_dew_point(hass: HomeAssistant) -> None:
    """Devices already reporting a dew point are left alone."""
    device = add_device(hass, "Weather")
    add_sensor(hass, device, "temperature", "temperature")
    add_sensor(hass, device, "humidity", "humidity")
    native = add_sensor(hass, device, "dew_point", "temperature")

    assert async_discover_sources(hass) == ()

    # ...unless that sensor is disabled.
    er.async_get(hass).async_update_entity(
        native.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    assert len(async_discover_sources(hass)) == 1


async def test_device_class_set_by_user(hass: HomeAssistant) -> None:
    """A device class overridden in the UI is taken into account."""
    device = add_device(hass, "Generic")
    temperature = add_sensor(hass, device, "value_1", None)
    add_sensor(hass, device, "value_2", "humidity")
    assert async_discover_sources(hass) == ()

    er.async_get(hass).async_update_entity(
        temperature.entity_id, device_class="temperature"
    )

    assert len(async_discover_sources(hass)) == 1


async def test_exclude(hass: HomeAssistant) -> None:
    """Excluded pairs are not returned."""
    device = add_device(hass, "Office")
    temperature = add_sensor(hass, device, "temperature", "temperature")
    humidity = add_sensor(hass, device, "humidity", "humidity")

    assert (
        async_discover_sources(
            hass, exclude={(temperature.entity_id, humidity.entity_id)}
        )
        == ()
    )
