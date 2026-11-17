"""Config flow for the Dew Point integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, Platform
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from . import async_discover_auto_sources
from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_MODE,
    CONF_TEMPERATURE_ENTITY,
    DOMAIN,
    MODE_AUTO,
    MODE_MANUAL,
)

# Config entry titles and default names are not translated by Home Assistant.
AUTO_TITLES = {"en": "Automatic detection", "fr": "Détection automatique"}
DEFAULT_NAMES = {"en": "Dew point", "fr": "Point de rosée"}


class DewPointConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the automatic detection, or a pair of sensors chosen by hand."""

    VERSION = 1

    def _localized(self, texts: dict[str, str]) -> str:
        """Return the text matching the language of the Home Assistant server."""
        return texts.get(self.hass.config.language.split("-")[0], texts["en"])

    def _auto_entry_exists(self) -> bool:
        """Return whether the automatic detection is already set up."""
        return any(
            entry.data[CONF_MODE] == MODE_AUTO
            for entry in self._async_current_entries(include_ignore=False)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a mode; only manual pairs can be added twice."""
        if self._auto_entry_exists():
            return await self.async_step_manual()
        return self.async_show_menu(
            step_id="user", menu_options=[MODE_AUTO, MODE_MANUAL]
        )

    async def async_step_auto(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a dew point sensor to every device measuring both quantities."""
        await self.async_set_unique_id(MODE_AUTO)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._localized(AUTO_TITLES), data={CONF_MODE: MODE_AUTO}
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a dew point sensor for two sensors chosen by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pair = {
                CONF_TEMPERATURE_ENTITY: user_input[CONF_TEMPERATURE_ENTITY],
                CONF_HUMIDITY_ENTITY: user_input[CONF_HUMIDITY_ENTITY],
            }
            self._async_abort_entries_match(pair)
            if self._auto_entry_exists() and any(
                source.temperature_entity_id == pair[CONF_TEMPERATURE_ENTITY]
                and source.humidity_entity_id == pair[CONF_HUMIDITY_ENTITY]
                for source in async_discover_auto_sources(self.hass)
            ):
                errors["base"] = "already_detected"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data={CONF_MODE: MODE_MANUAL, **pair}
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=self._localized(DEFAULT_NAMES)
                ): TextSelector(),
                vol.Required(CONF_TEMPERATURE_ENTITY): EntitySelector(
                    EntitySelectorConfig(
                        domain=Platform.SENSOR,
                        device_class=SensorDeviceClass.TEMPERATURE,
                    )
                ),
                vol.Required(CONF_HUMIDITY_ENTITY): EntitySelector(
                    EntitySelectorConfig(
                        domain=Platform.SENSOR,
                        device_class=SensorDeviceClass.HUMIDITY,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )
