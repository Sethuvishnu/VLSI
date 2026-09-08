"""
Thin-Film Deposition Module
-----------------------------
Simple linear/Arrhenius deposition rate models for common CVD/PVD/sputter
processes used in CMOS front-end and back-end steps (poly-Si, oxide,
nitride, metal).

thickness(t) = rate(T) * t
rate(T)      = R0 * exp(-Ea / kT)      (Arrhenius, rate-limited CVD)
"""

import numpy as np

K_BOLTZMANN_EV = 8.617333262e-5  # eV/K

# Approximate deposition parameters (illustrative, not process-qualified).
DEPOSITION_PARAMS = {
    # calibrated so rates land near realistic fab values at typical process temps
    "Polysilicon (LPCVD)": {"R0": 2.74e10, "Ea": 1.7},        # ~7 nm/min @ 620C
    "Silicon Nitride (LPCVD)": {"R0": 1.64e9, "Ea": 1.8},     # ~4 nm/min @ 780C
    "Silicon Dioxide (PECVD)": {"R0": 2.13e4, "Ea": 0.3},     # ~80 nm/min @ 350C
    "Aluminum (Sputter)": {"R0": None, "Ea": None},           # not thermally activated
}

# Sputtered/evaporated metals: rate set by power/pressure, treat as constant.
METAL_CONSTANT_RATE_NM_PER_MIN = 50.0


def deposition_rate(material, temperature_c=None):
    """Return deposition rate in nm/min for the chosen material."""
    p = DEPOSITION_PARAMS[material]
    if p["R0"] is None:
        return METAL_CONSTANT_RATE_NM_PER_MIN
    t_kelvin = temperature_c + 273.15
    return p["R0"] * np.exp(-p["Ea"] / (K_BOLTZMANN_EV * t_kelvin))


def film_thickness(time_min, material, temperature_c=None):
    """
    Film thickness (nm) vs. deposition time (minutes).
    time_min can be a scalar or array.
    """
    time_min = np.atleast_1d(np.asarray(time_min, dtype=float))
    rate = deposition_rate(material, temperature_c)
    return rate * time_min
