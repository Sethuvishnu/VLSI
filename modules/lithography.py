"""
Photolithography Module
--------------------------
Classic Rayleigh criteria used to size resolution and depth of focus
for a projection lithography system:

    Resolution (CD)   = k1 * lambda / NA
    Depth of Focus     = k2 * lambda / NA^2

k1, k2 are process-dependent constants (typically 0.4-0.8 for k1,
~0.5-1.0 for k2). Lower k1 needs more advanced RET (OPC, phase-shift
masks, immersion, multiple patterning) to stay manufacturable.
"""

WAVELENGTHS_NM = {
    "g-line (436 nm)": 436,
    "i-line (365 nm)": 365,
    "KrF (248 nm)": 248,
    "ArF (193 nm)": 193,
    "ArF immersion (193i nm)": 193,
    "EUV (13.5 nm)": 13.5,
}


def resolution_nm(wavelength_nm, numerical_aperture, k1=0.4):
    """Minimum resolvable feature size (nm), Rayleigh criterion."""
    return k1 * wavelength_nm / numerical_aperture


def depth_of_focus_nm(wavelength_nm, numerical_aperture, k2=0.5):
    """Depth of focus (nm) available at a given NA and wavelength."""
    return k2 * wavelength_nm / (numerical_aperture ** 2)
