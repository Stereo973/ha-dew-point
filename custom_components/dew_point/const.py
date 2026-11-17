"""Constants for the Dew Point integration."""

from typing import Final

DOMAIN: Final = "dew_point"

CONF_MODE: Final = "mode"
CONF_TEMPERATURE_ENTITY: Final = "temperature_entity"
CONF_HUMIDITY_ENTITY: Final = "humidity_entity"

# A single "auto" entry watches every device; "manual" entries hold one pair each.
MODE_AUTO: Final = "auto"
MODE_MANUAL: Final = "manual"

ATTR_TEMPERATURE_ENTITY: Final = "temperature_entity"
ATTR_HUMIDITY_ENTITY: Final = "humidity_entity"

# Seconds to wait after an entity registry change before looking for new pairs,
# so that all the sensors of a freshly added device are registered first.
RESCAN_DELAY: Final = 2.0
