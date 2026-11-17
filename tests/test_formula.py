"""Tests for the dew point formula."""

import math

import pytest

from custom_components.dew_point.formula import dew_point


@pytest.mark.parametrize(
    ("temperature", "humidity", "expected"),
    [
        # Reference values from psychrometric tables.
        (20.0, 50.0, 9.3),
        (25.0, 60.0, 16.7),
        (30.0, 70.0, 23.9),
        (10.0, 90.0, 8.4),
        (0.0, 50.0, -9.2),
        (-10.0, 80.0, -12.8),
        (35.0, 20.0, 8.7),
    ],
)
def test_reference_values(temperature: float, humidity: float, expected: float) -> None:
    """The formula matches published dew points within 0.15 °C."""
    assert dew_point(temperature, humidity) == pytest.approx(expected, abs=0.15)


def _buck_dew_point(temperature: float, humidity: float) -> float:
    """Reference: invert the Buck (1996) vapour pressure equation by bisection."""

    def saturation_pressure(value: float) -> float:
        return 6.1121 * math.exp((18.678 - value / 234.5) * (value / (257.14 + value)))

    target = humidity / 100 * saturation_pressure(temperature)
    low, high = -100.0, temperature
    for _ in range(80):
        middle = (low + high) / 2
        if saturation_pressure(middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def test_against_independent_equation() -> None:
    """The Magnus formula stays within 0.1 °C of the Buck equation."""
    for temperature in range(-20, 51, 5):
        for humidity in range(10, 101, 10):
            assert dew_point(temperature, humidity) == pytest.approx(
                _buck_dew_point(temperature, humidity), abs=0.1
            )


@pytest.mark.parametrize("temperature", [-30.0, -5.0, 0.0, 18.5, 42.0])
def test_saturated_air(temperature: float) -> None:
    """At 100 % humidity (or more) the dew point is the air temperature."""
    assert dew_point(temperature, 100.0) == pytest.approx(temperature)
    assert dew_point(temperature, 104.0) == pytest.approx(temperature)


def test_dew_point_is_below_temperature() -> None:
    """The dew point rises with humidity and never exceeds the temperature."""
    values = [dew_point(22.0, humidity) for humidity in range(1, 101)]
    assert values == sorted(values)
    assert values[-1] == pytest.approx(22.0)


@pytest.mark.parametrize(
    ("temperature", "humidity"),
    [(20.0, 0.0), (20.0, -5.0), (math.nan, 50.0), (20.0, math.inf), (-300.0, 50.0)],
)
def test_undefined(temperature: float, humidity: float) -> None:
    """Inputs without a dew point return None instead of raising."""
    assert dew_point(temperature, humidity) is None
