"""
Ion Implantation Module
-------------------------
Approximates the as-implanted dopant profile as a Gaussian, characterised
by the projected range Rp and straggle (standard deviation) dRp:

    N(x) = Np * exp( -(x - Rp)^2 / (2 * dRp^2) )
    Np   = Dose / (sqrt(2*pi) * dRp)

Rp and dRp normally come from SRIM/TRIM Monte-Carlo tables or LSS theory.
This module uses a simplified power-law fit (Rp, dRp proportional to
E^0.7-ish) tuned to roughly match published Boron/Phosphorus/Arsenic
implant tables for teaching purposes. Replace with a lookup table or
SRIM data for research-grade accuracy.
"""

import numpy as np

# Simplified empirical fit: Rp (um) = k_r * E(keV)^p_r
# dRp (um) = frac * Rp   (straggle as a fraction of range)
IMPLANT_PARAMS = {
    "Boron":      {"k_r": 0.0037, "p_r": 0.79, "straggle_frac": 0.45},
    "Phosphorus": {"k_r": 0.0019, "p_r": 0.75, "straggle_frac": 0.40},
    "Arsenic":    {"k_r": 0.0011, "p_r": 0.70, "straggle_frac": 0.30},
}


def projected_range(energy_kev, dopant="Boron"):
    """Return (Rp, dRp) in micrometers for a given implant energy (keV)."""
    p = IMPLANT_PARAMS[dopant]
    Rp = p["k_r"] * (energy_kev ** p["p_r"])
    dRp = p["straggle_frac"] * Rp
    return Rp, dRp


def implant_profile(x_um, energy_kev, dose_cm2, dopant="Boron"):
    """
    Gaussian as-implanted profile.
    x_um       : depth array (um)
    energy_kev : implant energy (keV)
    dose_cm2   : implant dose (ions/cm^2)
    Returns N(x) in cm^-3.
    """
    x_um = np.asarray(x_um, dtype=float)
    Rp, dRp = projected_range(energy_kev, dopant)

    dRp_cm = dRp * 1e-4
    Np = dose_cm2 / (np.sqrt(2 * np.pi) * dRp_cm)  # peak concentration, cm^-3

    profile = Np * np.exp(-((x_um - Rp) ** 2) / (2 * dRp ** 2))
    return profile, Rp, dRp
