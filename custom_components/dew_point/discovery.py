"""Find the temperature / humidity sensor pairs to compute a dew point from."""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
import re
import unicodedata

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


@dataclass(frozen=True, slots=True)
class DewPointSource:
    """A temperature / humidity pair a dew point sensor is computed from."""

    unique_id: str
    temperature_entity_id: str
    humidity_entity_id: str
    # Device the dew point sensor is attached to, if any.
    device_id: str | None = None
    # Entity name typed by the user (manual pairs); automatic pairs are translated.
    name: str | None = None
    # Tells apart the pairs of a device which has several ("Outdoor", "2"...).
    label: str | None = None


type Pair = tuple[er.RegistryEntry, er.RegistryEntry]

# Words naming the measurement in entity names, IDs and translation keys
# (lower case, without accents). Two sensors "play the same role" on a device
# when their identifiers only differ by these words:
# "Outdoor temperature" <-> "Outdoor humidity".
_ROLE_WORDS = (
    # temperature
    "temperature",
    "temperatura",
    "temperatur",
    "temperatuur",
    "temp",
    # humidity
    "relative humidity",
    "relative_humidity",
    "humidity",
    "humidite",
    "humedad",
    "umidita",
    "umidade",
    "luftfeuchtigkeit",
    "feuchtigkeit",
    "luchtvochtigheid",
    "vochtigheid",
    "humid",
    "hum",
    "rh",
)
_ROLE_RE = re.compile("|".join(sorted(_ROLE_WORDS, key=len, reverse=True)))
_DEW_POINT_RE = re.compile(
    r"dew[ _-]?point|point[ _-]de[ _-]rosee|taupunkt|punto[ _-]de[ _-]rocio|dauwpunt"
)


def _normalize(text: str) -> str:
    """Lower case and strip accents."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _device_class(entry: er.RegistryEntry) -> str | None:
    """Return the device class, honoring the one set by the user."""
    return entry.device_class or entry.original_device_class


def _measurements(
    entries: list[er.RegistryEntry], device_class: SensorDeviceClass
) -> list[er.RegistryEntry]:
    """Return the sensors measuring `device_class`, skipping diagnostic ones.

    Diagnostic temperature sensors report things like a chip or battery
    temperature, not the ambient air.
    """
    return [
        entry
        for entry in entries
        if _device_class(entry) == device_class and entry.entity_category is None
    ]


def _is_dew_point(entry: er.RegistryEntry) -> bool:
    """Return whether the sensor already is a dew point provided by the device."""
    return any(
        isinstance(text, str) and _DEW_POINT_RE.search(_normalize(text))
        for text in (entry.translation_key, entry.original_name, entry.unique_id)
    )


def _same_role(temperature: er.RegistryEntry, humidity: er.RegistryEntry) -> bool:
    """Return whether both sensors measure the same spot, judging by their names."""
    for attribute in ("translation_key", "original_name", "unique_id", "entity_id"):
        first = getattr(temperature, attribute)
        second = getattr(humidity, attribute)
        if not (isinstance(first, str) and isinstance(second, str)):
            continue
        if _ROLE_RE.sub("*", _normalize(first)) == _ROLE_RE.sub(
            "*", _normalize(second)
        ):
            return True
    return False


def _pair(
    temperatures: list[er.RegistryEntry], humidities: list[er.RegistryEntry]
) -> list[Pair]:
    """Match each humidity sensor with the temperature sensor of the same spot."""
    if len(temperatures) == 1 and len(humidities) == 1:
        return [(temperatures[0], humidities[0])]

    # Several candidates (indoor / outdoor, extra probes...): only keep the
    # matches the names make unambiguous.
    pairs: list[Pair] = []
    for humidity in humidities:
        matches = [temp for temp in temperatures if _same_role(temp, humidity)]
        if len(matches) == 1:
            pairs.append((matches[0], humidity))
    return pairs


def _label(entry: er.RegistryEntry) -> str | None:
    """Return what is left of the sensor name once the measurement is removed."""
    name = entry.name or entry.original_name or ""
    words = [word for word in name.split() if not _ROLE_RE.fullmatch(_normalize(word))]
    return " ".join(words) or None


def _labels(pairs: list[Pair]) -> list[str | None]:
    """Return a label per pair; None when the device only has one."""
    if len(pairs) < 2:
        return [None] * len(pairs)
    labels = [_label(temperature) for temperature, _ in pairs]
    if None in labels or len(set(labels)) != len(labels):
        return [str(index) for index in range(1, len(pairs) + 1)]
    return labels


@callback
def async_discover_sources(
    hass: HomeAssistant, exclude: Collection[tuple[str, str]] = ()
) -> tuple[DewPointSource, ...]:
    """Return a source for each device having a temperature and a humidity sensor.

    Devices which already provide a dew point sensor are left alone, and so are
    the (temperature, humidity) entity ID pairs listed in `exclude`.
    """
    by_device: dict[str, list[er.RegistryEntry]] = defaultdict(list)
    for entry in er.async_get(hass).entities.values():
        if (
            entry.domain == Platform.SENSOR
            and entry.device_id is not None
            and entry.platform != DOMAIN
            and entry.disabled_by is None
        ):
            by_device[entry.device_id].append(entry)

    sources: list[DewPointSource] = []
    for device_id, entries in by_device.items():
        if any(_is_dew_point(entry) for entry in entries):
            continue

        entries.sort(key=lambda entry: entry.id)
        pairs = [
            (temperature, humidity)
            for temperature, humidity in _pair(
                _measurements(entries, SensorDeviceClass.TEMPERATURE),
                _measurements(entries, SensorDeviceClass.HUMIDITY),
            )
            if (temperature.entity_id, humidity.entity_id) not in exclude
        ]
        sources.extend(
            DewPointSource(
                unique_id=f"{temperature.id}_{humidity.id}",
                temperature_entity_id=temperature.entity_id,
                humidity_entity_id=humidity.entity_id,
                device_id=device_id,
                label=label,
            )
            for (temperature, humidity), label in zip(
                pairs, _labels(pairs), strict=True
            )
        )

    return tuple(sorted(sources, key=lambda source: source.unique_id))
