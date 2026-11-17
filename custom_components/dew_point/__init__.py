"""Dew point sensors computed from temperature and humidity sensors."""

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_MODE,
    CONF_TEMPERATURE_ENTITY,
    DOMAIN,
    MODE_AUTO,
    MODE_MANUAL,
    RESCAN_DELAY,
)
from .discovery import DewPointSource, async_discover_sources

PLATFORMS = [Platform.SENSOR]

type DewPointConfigEntry = ConfigEntry[tuple[DewPointSource, ...]]


async def async_setup_entry(hass: HomeAssistant, entry: DewPointConfigEntry) -> bool:
    """Set up the automatic detection or a manual pair."""
    if entry.data[CONF_MODE] == MODE_AUTO:
        entry.runtime_data = async_discover_auto_sources(hass)
        _async_remove_stale_entities(hass, entry)
        _async_watch_devices(hass, entry)
    else:
        entry.runtime_data = (_async_manual_source(hass, entry),)
        _async_follow_renames(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DewPointConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def async_discover_auto_sources(hass: HomeAssistant) -> tuple[DewPointSource, ...]:
    """Return the pairs found on devices, minus the ones set up manually."""
    manual_pairs = {
        (entry.data[CONF_TEMPERATURE_ENTITY], entry.data[CONF_HUMIDITY_ENTITY])
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data[CONF_MODE] == MODE_MANUAL
    }
    return async_discover_sources(hass, exclude=manual_pairs)


@callback
def _async_manual_source(
    hass: HomeAssistant, entry: DewPointConfigEntry
) -> DewPointSource:
    """Return the pair chosen by the user."""
    temperature = entry.data[CONF_TEMPERATURE_ENTITY]
    humidity = entry.data[CONF_HUMIDITY_ENTITY]
    # Only attach the sensor to a device when both measurements come from it.
    registry = er.async_get(hass)
    devices = {
        registry_entry.device_id
        if (registry_entry := registry.async_get(entity_id))
        else None
        for entity_id in (temperature, humidity)
    }
    device_id = devices.pop() if len(devices) == 1 else None
    return DewPointSource(
        unique_id=entry.entry_id,
        temperature_entity_id=temperature,
        humidity_entity_id=humidity,
        device_id=device_id,
        name=entry.title,
    )


@callback
def _async_remove_stale_entities(
    hass: HomeAssistant, entry: DewPointConfigEntry
) -> None:
    """Remove the dew point sensors whose temperature / humidity pair is gone."""
    registry = er.async_get(hass)
    current = {source.unique_id for source in entry.runtime_data}
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.unique_id not in current:
            registry.async_remove(registry_entry.entity_id)


@callback
def _is_sensor_event(event_data: er.EventEntityRegistryUpdatedData) -> bool:
    """Filter the entity registry events down to sensors."""
    return event_data["entity_id"].startswith("sensor.")


@callback
def _async_watch_devices(hass: HomeAssistant, entry: DewPointConfigEntry) -> None:
    """Reload the automatic entry when the set of pairs on devices changes.

    Covers devices being added or removed, sensors being renamed, enabled,
    disabled or moved, and device classes being overridden.
    """
    cancel_rescan: CALLBACK_TYPE | None = None

    @callback
    def async_rescan(_now: datetime) -> None:
        nonlocal cancel_rescan
        cancel_rescan = None
        if async_discover_auto_sources(hass) != entry.runtime_data:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    @callback
    def async_registry_updated(
        _event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        nonlocal cancel_rescan
        if cancel_rescan is not None:
            cancel_rescan()
        cancel_rescan = async_call_later(hass, RESCAN_DELAY, async_rescan)

    @callback
    def async_cancel_rescan() -> None:
        if cancel_rescan is not None:
            cancel_rescan()

    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            async_registry_updated,
            event_filter=_is_sensor_event,
        )
    )
    entry.async_on_unload(async_cancel_rescan)


@callback
def _async_follow_renames(hass: HomeAssistant, entry: DewPointConfigEntry) -> None:
    """Keep a manual pair working when one of its source entity IDs changes."""

    @callback
    def async_registry_updated(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] != "update" or "old_entity_id" not in event.data:
            return
        renamed = {
            key: event.data["entity_id"]
            for key in (CONF_TEMPERATURE_ENTITY, CONF_HUMIDITY_ENTITY)
            if entry.data[key] == event.data["old_entity_id"]
        }
        if renamed:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, **renamed}
            )
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            async_registry_updated,
            event_filter=_is_sensor_event,
        )
    )
