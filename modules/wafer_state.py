"""
WaferState: the one object that makes this a *simulator* instead of
seven separate calculators.

Every process step function here takes a WaferState in and returns the
*same* WaferState, mutated to reflect what that step did. Streamlit tabs
all read and write st.session_state["wafer"], so moving from tab 2 to
tab 4 carries forward whatever oxide/implant/diffusion history came
before it, the same way a real wafer physically carries its own history
through a fab line.

Key design choice: doping is tracked on a FIXED depth grid (self.x_um)
that every step shares. That is what lets diffusion "see" an implant
that happened two tabs earlier, add the implant's Gaussian onto the
background doping, and diffuse the combined profile, instead of each
tab starting from a blank np.zeros() array.
"""

import copy
import numpy as np

from . import oxidation, diffusion, implantation, deposition, etching, lithography

DEPTH_GRID_UM = np.linspace(0, 3.0, 600)  # shared 1D depth axis, 0 to 3 um


class Layer:
    """One deposited/grown film on top of the substrate."""
    def __init__(self, name, kind, thickness_um):
        self.name = name
        self.kind = kind              # "oxide" | "polysilicon" | "nitride" | "metal"
        self.thickness_um = thickness_um

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "thickness": self.thickness_um}


class WaferState:
    """
    The single persistent object representing 'the wafer' as it moves
    through the process flow. Create one with WaferState.fresh() at the
    start of a run; every step function below mutates and returns it.
    """

    def __init__(self):
        # --- identity from Wafer Prep ---
        self.diameter_mm = 200
        self.orientation = "<100>"
        self.substrate_type = "p-type (Boron)"
        self.substrate_resistivity = 10.0
        self.background_doping_cm3 = 1e15  # typical for ~10-15 ohm-cm Si

        # --- layer stack, bottom (substrate) implied, then grown upward ---
        self.layers = []  # list[Layer]

        # --- doping state on the shared depth grid ---
        self.x_um = DEPTH_GRID_UM
        self.net_doping_cm3 = np.full_like(self.x_um, self.background_doping_cm3)
        self.last_implant_dose_cm2 = None   # feeds diffusion's drive-in mode
        self.last_implant_dopant = None

        # --- process history log, shown in the UI so the run is auditable ---
        self.history = []  # list[str]

    @staticmethod
    def fresh():
        return WaferState()

    def clone(self):
        return copy.deepcopy(self)

    def log(self, message):
        self.history.append(message)

    def total_oxide_um(self):
        return sum(l.thickness_um for l in self.layers if l.kind == "oxide")

    def top_layer_name(self):
        return self.layers[-1].name if self.layers else "Bare Silicon"


# ---------------------------------------------------------------------------
# Step functions. Each takes (wafer, **params), mutates wafer in place,
# logs what happened, and returns wafer so calls can be chained:
#   wafer = step_oxidation(step_wafer_prep(WaferState.fresh(), ...), ...)
# ---------------------------------------------------------------------------

def step_wafer_prep(wafer, diameter_mm, orientation, substrate_type, resistivity):
    wafer.diameter_mm = diameter_mm
    wafer.orientation = orientation
    wafer.substrate_type = substrate_type
    wafer.substrate_resistivity = resistivity
    # Rough resistivity -> background doping conversion for p-type Si
    # (illustrative inverse relationship, not a precise mobility model)
    wafer.background_doping_cm3 = max(1e14, 1.5e16 / max(resistivity, 0.01))
    wafer.net_doping_cm3 = np.full_like(wafer.x_um, wafer.background_doping_cm3)
    wafer.log(f"Wafer prep: {diameter_mm}mm {orientation} {substrate_type}, "
              f"{resistivity:.2f} ohm-cm -> background doping "
              f"{wafer.background_doping_cm3:.2e} cm^-3")
    return wafer


def step_oxidation(wafer, temperature_c, time_hr, ambient):
    # Consumes "existing oxide" as the starting point, so repeated
    # oxidation steps correctly continue from where the last one left off.
    existing_oxide_um = wafer.total_oxide_um()
    thickness_um = oxidation.oxide_thickness(
        time_hr, temperature_c, ambient, initial_oxide_um=existing_oxide_um
    )[0]
    # new oxide grown by *this* step = new total - what was already there
    grown_um = max(thickness_um - existing_oxide_um, 0.0)
    wafer.layers.append(Layer("SiO2", "oxide", grown_um))
    wafer.log(f"Oxidation: {ambient} O2 at {temperature_c}C for {time_hr}hr -> "
              f"+{grown_um*1000:.1f}nm oxide (total oxide {thickness_um*1000:.1f}nm)")
    return wafer


def step_implantation(wafer, dopant, energy_kev, dose_cm2):
    profile, Rp, dRp = implantation.implant_profile(wafer.x_um, energy_kev, dose_cm2, dopant)
    # Add the implant on top of whatever doping is already on the grid,
    # instead of overwriting it -- this is the step that actually makes
    # "chained" meaningful: an earlier diffusion's tail is still there.
    wafer.net_doping_cm3 = wafer.net_doping_cm3 + profile
    wafer.last_implant_dose_cm2 = dose_cm2
    wafer.last_implant_dopant = dopant
    wafer.log(f"Implantation: {dopant} at {energy_kev}keV, dose {dose_cm2:.1e}cm^-2 -> "
              f"Rp={Rp*1000:.1f}nm, peak added {profile.max():.2e}cm^-3")
    return wafer


def step_diffusion(wafer, temperature_c, time_min, mode, dopant=None, surface_conc_cm3=None):
    dopant = dopant or wafer.last_implant_dopant or "Boron"
    if mode == "drive_in":
        dose = wafer.last_implant_dose_cm2 or 1e14
        added = diffusion.drive_in_profile(wafer.x_um, time_min * 60, temperature_c, dose, dopant)
        # Drive-in redistributes an existing fixed dose -- replace the
        # implant's sharp Gaussian with its diffused (spread-out) shape,
        # rather than adding a second independent dose on top of it.
        wafer.net_doping_cm3 = wafer.net_doping_cm3 - (
            implantation.implant_profile(wafer.x_um, 50, dose, dopant)[0]
            if wafer.last_implant_dose_cm2 else 0
        )
        wafer.net_doping_cm3 = np.clip(wafer.net_doping_cm3, wafer.background_doping_cm3, None) + added
    else:
        cs = surface_conc_cm3 or 1e20
        added = diffusion.predeposition_profile(wafer.x_um, time_min * 60, temperature_c, cs, dopant)
        wafer.net_doping_cm3 = wafer.net_doping_cm3 + added

    xj = diffusion.junction_depth(wafer.x_um, wafer.net_doping_cm3, wafer.background_doping_cm3)
    wafer.log(f"Diffusion ({mode}): {dopant} at {temperature_c}C for {time_min}min -> "
              f"junction depth {xj:.3f}um" if xj else
              f"Diffusion ({mode}): {dopant} at {temperature_c}C for {time_min}min")
    return wafer


def step_deposition(wafer, material, temperature_c, time_min):
    thickness_nm = deposition.film_thickness(time_min, material, temperature_c)[0]
    kind = ("polysilicon" if "poly" in material.lower()
            else "nitride" if "nitride" in material.lower()
            else "metal" if "alum" in material.lower()
            else "oxide")
    name = material.split(" (")[0]
    wafer.layers.append(Layer(name, kind, thickness_nm / 1000.0))
    wafer.log(f"Deposition: {material} for {time_min}min -> +{thickness_nm:.1f}nm")
    return wafer


def step_etching(wafer, process, time_min, mask_opening_nm, mask_thickness_nm):
    depth_nm, undercut_nm = etching.etch_profile(time_min, process, mask_opening_nm)
    # Remove material from the top layer(s) down to the etch depth.
    remaining_depth_um = depth_nm / 1000.0
    new_layers = []
    for layer in reversed(wafer.layers):
        if remaining_depth_um <= 0:
            new_layers.append(layer)
            continue
        if layer.thickness_um <= remaining_depth_um:
            remaining_depth_um -= layer.thickness_um
            # fully etched away -- drop it
        else:
            layer.thickness_um -= remaining_depth_um
            remaining_depth_um = 0
            new_layers.append(layer)
    wafer.layers = list(reversed(new_layers))
    wafer.log(f"Etching: {process} for {time_min}min -> {depth_nm:.1f}nm deep, "
              f"{undercut_nm:.1f}nm undercut per side")
    return wafer, depth_nm, undercut_nm