"""
Thermal Oxidation Module
-------------------------
Implements the Deal-Grove model for SiO2 growth on silicon.

x_ox(t)^2 + A * x_ox(t) = B * (t + tau)

where:
    B    = parabolic rate constant (um^2/hr), Arrhenius in T
    B/A  = linear rate constant   (um/hr),   Arrhenius in T
    tau  = time shift to account for any pre-existing oxide thickness

Rate constants below are the standard textbook values for <111> silicon
(Deal & Grove, 1965 / Plummer, Deal, Griffin "Silicon VLSI Technology").
They are good for teaching purposes; production fabs calibrate these
empirically for their own furnaces and orientations.
"""

import numpy as np

K_BOLTZMANN_EV = 8.617333262e-5  # eV/K

# Arrhenius parameters: rate = C * exp(-Ea / (k*T))
OXIDATION_PARAMS = {
    "dry": {  # dry O2 ambient
        "B":   {"C": 7.72e2, "Ea": 1.23},   # um^2/hr
        "B_A": {"C": 6.23e6, "Ea": 2.00},   # um/hr
    },
    "wet": {  # steam / wet O2 ambient (faster growth)
        "B":   {"C": 2.14e2, "Ea": 0.71},
        "B_A": {"C": 8.95e7, "Ea": 2.05},
    },
}


def _arrhenius(params, temperature_c):
    """Evaluate C * exp(-Ea / kT) for a given temperature in Celsius."""
    t_kelvin = temperature_c + 273.15
    return params["C"] * np.exp(-params["Ea"] / (K_BOLTZMANN_EV * t_kelvin))


def rate_constants(temperature_c, ambient="dry"):
    """Return (B, B/A) rate constants at a given temperature."""
    p = OXIDATION_PARAMS[ambient]
    B = _arrhenius(p["B"], temperature_c)
    B_A = _arrhenius(p["B_A"], temperature_c)
    return B, B_A


def oxide_thickness(time_hr, temperature_c, ambient="dry", initial_oxide_um=0.0):
    """
    Deal-Grove oxide thickness vs. time.

    time_hr           : array-like or scalar, oxidation time in hours
    temperature_c      : oxidation temperature in Celsius
    ambient            : 'dry' or 'wet'
    initial_oxide_um   : pre-existing oxide thickness (native oxide etc.)

    Returns oxide thickness in micrometers.
    """
    time_hr = np.atleast_1d(np.asarray(time_hr, dtype=float))
    B, B_A = rate_constants(temperature_c, ambient)
    A = B / B_A

    # tau shifts the curve so that x(0) = initial_oxide_um
    tau = (initial_oxide_um ** 2 + A * initial_oxide_um) / B

    x = (A / 2.0) * (np.sqrt(1.0 + (time_hr + tau) / (A ** 2 / (4 * B))) - 1.0)
    return x


def growth_regime(time_hr, temperature_c, ambient="dry"):
    """
    Classify growth as 'linear' (thin oxide, reaction-limited) or
    'parabolic' (thick oxide, diffusion-limited) based on A^2/4B.
    """
    B, B_A = rate_constants(temperature_c, ambient)
    A = B / B_A
    crossover_time = A ** 2 / (4 * B)
    return "linear" if time_hr < crossover_time else "parabolic", crossover_time
