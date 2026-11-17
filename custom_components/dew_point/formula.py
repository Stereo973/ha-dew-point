"""Dew point calculation (Magnus formula)."""

import math

# Magnus coefficients from Alduchov & Eskridge (1996).
# Relative error below 0.4 % between -40 °C and +50 °C.
MAGNUS_A = 17.625
MAGNUS_B = 243.04  # °C


def dew_point(temperature: float, humidity: float) -> float | None:
    """Return the dew point in °C.

    temperature: air temperature in °C.
    humidity: relative humidity in % (values above 100 are treated as 100).

    Returns None when the dew point is undefined: humidity of 0 % or less,
    non-finite input, or a temperature outside the domain of the formula.
    """
    if not (math.isfinite(temperature) and math.isfinite(humidity)):
        return None
    if humidity <= 0 or temperature <= -MAGNUS_B:
        return None

    humidity = min(humidity, 100.0)
    gamma = math.log(humidity / 100.0) + MAGNUS_A * temperature / (
        MAGNUS_B + temperature
    )
    return MAGNUS_B * gamma / (MAGNUS_A - gamma)
