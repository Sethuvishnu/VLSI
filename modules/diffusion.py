"""
Dopant Diffusion Module
------------------------
Two classic diffusion scenarios from Fick's laws:

1) Predeposition (constant surface concentration, semi-infinite solid):
       C(x,t) = Cs * erfc( x / (2*sqrt(D*t)) )

2) Drive-in (fixed total dose Q, limited source -> Gaussian):
       C(x,t) = [Q / sqrt(pi*D*t)] * exp( -x^2 / (4*D*t) )

D follows an Arrhenius temperature dependence: D = D0 * exp(-Ea / kT)
"""

import numpy as np
from scipy.special import erfc

K_BOLTZMANN_EV = 8.617333262e-5  # eV/K

# Approximate diffusivity parameters for common dopants in silicon.
# (Educational/typical textbook values - real fabs use calibrated data.)
DIFFUSION_PARAMS = {
    "Boron":       {"D0": 0.76,  "Ea": 3.46},   # cm^2/s, eV
    "Phosphorus":  {"D0": 3.85,  "Ea": 3.66},
    "Arsenic":     {"D0": 0.066, "Ea": 3.44},
    "Antimony":    {"D0": 0.214, "Ea": 3.65},
}


def diffusivity(temperature_c, dopant="Boron"):
    """Diffusion coefficient D (cm^2/s) at a given temperature (Celsius)."""
    p = DIFFUSION_PARAMS[dopant]
    t_kelvin = temperature_c + 273.15
    return p["D0"] * np.exp(-p["Ea"] / (K_BOLTZMANN_EV * t_kelvin))


def predeposition_profile(x_um, time_s, temperature_c, surface_conc_cm3, dopant="Boron"):
    """
    Constant-source diffusion profile (erfc).
    x_um            : depth array in micrometers
    time_s          : diffusion time in seconds
    surface_conc_cm3: fixed surface concentration Cs (cm^-3)
    Returns concentration profile C(x) in cm^-3.
    """
    x_cm = np.asarray(x_um, dtype=float) * 1e-4
    D = diffusivity(temperature_c, dopant)
    arg = x_cm / (2.0 * np.sqrt(D * time_s))
    return surface_conc_cm3 * erfc(arg)


def drive_in_profile(x_um, time_s, temperature_c, dose_cm2, dopant="Boron"):
    """
    Limited-source diffusion profile (Gaussian), for a fixed dose Q (cm^-2)
    already deposited near the surface (e.g., after predeposition or implant).
    Returns concentration profile C(x) in cm^-3.
    """
    x_cm = np.asarray(x_um, dtype=float) * 1e-4
    D = diffusivity(temperature_c, dopant)
    prefactor = dose_cm2 / np.sqrt(np.pi * D * time_s)
    return prefactor * np.exp(-(x_cm ** 2) / (4.0 * D * time_s))


def junction_depth(x_um, concentration, background_conc_cm3):
    """
    Find the junction depth: where the dopant profile crosses the
    background (substrate) doping concentration.
    """
    x_um = np.asarray(x_um)
    concentration = np.asarray(concentration)
    diff = concentration - background_conc_cm3
    sign_change = np.where(np.diff(np.sign(diff)) != 0)[0]
    if len(sign_change) == 0:
        return None
    i = sign_change[0]
    x0, x1 = x_um[i], x_um[i + 1]
    d0, d1 = diff[i], diff[i + 1]
    return x0 - d0 * (x1 - x0) / (d1 - d0)
