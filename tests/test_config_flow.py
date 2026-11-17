"""Tests for the config flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.dew_point.const import (
    CONF_HUMIDITY_ENTITY,
    CONF_MODE,
    CONF_TEMPERATURE_ENTITY,
    DOMAIN,
    MODE_AUTO,
    MODE_MANUAL,
)

from . import add_device, add_sensor, setup_auto

MANUAL_INPUT = {
    "name": "Cellar dew point",
    CONF_TEMPERATURE_ENTITY: "sensor.cellar_t",
    CONF_HUMIDITY_ENTITY: "sensor.cellar_h",
}


async def test_auto(hass: HomeAssistant) -> None:
    """The menu offers the automatic detection, which needs no input."""
    device = add_device(hass, "Living room")
    add_sensor(hass, device, "temperature", "temperature", state="20")
    add_sensor(hass, device, "humidity", "humidity", state="50")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [MODE_AUTO, MODE_MANUAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": MODE_AUTO}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Automatic detection"
    assert result["data"] == {CONF_MODE: MODE_AUTO}
    assert hass.states.get("sensor.living_room_dew_point") is not None


async def test_auto_title_follows_language(hass: HomeAssistant) -> None:
    """The entry is named in French on a French Home Assistant."""
    hass.config.language = "fr"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": MODE_AUTO}
    )

    assert result["title"] == "Détection automatique"


async def test_manual(hass: HomeAssistant) -> None:
    """A manual pair is created from the form."""
    hass.states.async_set("sensor.cellar_t", "12", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.cellar_h", "85", {"unit_of_measurement": "%"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": MODE_MANUAL}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MANUAL_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cellar dew point"
    assert result["data"] == {
        CONF_MODE: MODE_MANUAL,
        CONF_TEMPERATURE_ENTITY: "sensor.cellar_t",
        CONF_HUMIDITY_ENTITY: "sensor.cellar_h",
    }
    assert hass.states.get("sensor.cellar_dew_point") is not None


async def test_manual_pair_already_configured(hass: HomeAssistant) -> None:
    """The same pair cannot be added twice."""
    for _ in range(2):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": MODE_MANUAL}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MANUAL_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_only_manual_once_auto_is_set_up(hass: HomeAssistant) -> None:
    """With the automatic detection in place, the flow goes straight to the form."""
    device = add_device(hass, "Living room")
    temperature = add_sensor(hass, device, "temperature", "temperature", state="20")
    humidity = add_sensor(hass, device, "humidity", "humidity", state="50")
    await setup_auto(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    # A pair handled by the automatic detection is refused...
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Duplicate",
            CONF_TEMPERATURE_ENTITY: temperature.entity_id,
            CONF_HUMIDITY_ENTITY: humidity.entity_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_detected"}

    # ...and the form can be corrected.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MANUAL_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
