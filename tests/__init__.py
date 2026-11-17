"""Tests for the Dew Point integration."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dew_point.const import CONF_MODE, DOMAIN, MODE_AUTO


def add_device(hass: HomeAssistant, name: str) -> dr.DeviceEntry:
    """Register a device owned by another integration."""
    owner = MockConfigEntry(domain="test")
    owner.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=owner.entry_id, identifiers={("test", name)}, name=name
    )


def add_sensor(
    hass: HomeAssistant,
    device: dr.DeviceEntry | None,
    key: str,
    device_class: str | None,
    *,
    state: str | None = None,
    unit: str | None = None,
    **kwargs: Any,
) -> er.RegistryEntry:
    """Register a sensor of another integration, optionally with a state."""
    prefix = slugify(device.name) if device else "standalone"
    kwargs.setdefault("original_name", key.replace("_", " ").capitalize())
    entry = er.async_get(hass).async_get_or_create(
        "sensor",
        "test",
        f"{prefix}_{key}",
        suggested_object_id=f"{prefix}_{key}",
        device_id=device.id if device else None,
        original_device_class=device_class,
        **kwargs,
    )
    if state is not None:
        if unit is None:
            unit = "%" if device_class == "humidity" else "°C"
        hass.states.async_set(entry.entity_id, state, {"unit_of_measurement": unit})
    return entry


async def setup_auto(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the automatic detection."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MODE_AUTO, data={CONF_MODE: MODE_AUTO}, title="Auto"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
