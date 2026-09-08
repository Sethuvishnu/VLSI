"""
Etching Module
---------------
Basic isotropic vs. anisotropic etch models plus mask selectivity.

Etch depth(t) = rate * t
Anisotropy factor A_f = 1 - (lateral_rate / vertical_rate)
    A_f = 1   -> perfectly anisotropic (vertical walls, e.g. RIE)
    A_f = 0   -> perfectly isotropic (wet etch, undercuts equally)
"""

import numpy as np

ETCH_PARAMS = {
    "Wet Etch (isotropic, HF/BOE on SiO2)": {
        "vertical_rate_nm_min": 100.0,
        "anisotropy": 0.0,
        "selectivity_to_mask": 10.0,
    },
    "Plasma / RIE (anisotropic)": {
        "vertical_rate_nm_min": 150.0,
        "anisotropy": 0.9,
        "selectivity_to_mask": 20.0,
    },
    "DRIE (Bosch, highly anisotropic)": {
        "vertical_rate_nm_min": 2000.0,
        "anisotropy": 0.98,
        "selectivity_to_mask": 100.0,
    },
}


def etch_profile(time_min, process, mask_opening_nm):
    """
    Returns (vertical_depth_nm, lateral_undercut_nm) for a given etch time.
    mask_opening_nm is the lithographically defined opening width, used only
    to visualize the resulting trench shape.
    """
    p = ETCH_PARAMS[process]
    vertical_rate = p["vertical_rate_nm_min"]
    lateral_rate = vertical_rate * (1.0 - p["anisotropy"])

    depth = vertical_rate * time_min
    undercut = lateral_rate * time_min
    return depth, undercut


def mask_erosion(time_min, process, mask_thickness_nm):
    """Estimate remaining mask thickness after etch, given selectivity."""
    p = ETCH_PARAMS[process]
    mask_etch_rate = p["vertical_rate_nm_min"] / p["selectivity_to_mask"]
    remaining = mask_thickness_nm - mask_etch_rate * time_min
    return max(remaining, 0.0)
