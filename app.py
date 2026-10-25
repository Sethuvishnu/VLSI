"""
Virtual CMOS Fabrication Process Simulator
=============================================
An interactive, educational Python/Streamlit app that walks through the
major steps of CMOS fabrication, with a single wafer state that persists
and accumulates as you move through the 7 steps:

    1. Wafer Preparation
    2. Thermal Oxidation      (Deal-Grove model)
    3. Photolithography       (Rayleigh resolution / DoF)
    4. Ion Implantation       (Gaussian profile)
    5. Diffusion              (predeposition / drive-in)
    6. Thin-Film Deposition   (Arrhenius growth rate)
    7. Etching                (isotropic vs anisotropic)

Each tab lets you preview a step's physics by moving sliders, then an
"Apply to Wafer" button commits that step onto the shared WaferState in
st.session_state, so later tabs see what earlier tabs actually did.

Run with:
    pip install -r requirements.txt
    streamlit run app.py
"""

import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from modules import oxidation, diffusion, implantation, deposition, etching, lithography
from modules.wafer_view import draw_wafer_stack
from modules.wafer_state import (
    WaferState, step_wafer_prep, step_oxidation, step_implantation,
    step_diffusion, step_deposition, step_etching,
)

st.set_page_config(page_title="CMOS Fabrication Simulator", layout="wide")

# ---------------------------------------------------------------------------
# Shared wafer state. Created once per browser session, then every tab's
# "Apply to Wafer" button mutates this same object. This is what makes
# the app one continuous fabrication run instead of 7 disconnected tools.
# ---------------------------------------------------------------------------
if "wafer" not in st.session_state:
    st.session_state.wafer = WaferState.fresh()

wafer = st.session_state.wafer

st.title("🔬 Virtual CMOS Fabrication Process Simulator")
st.caption(
    "An educational, open-source tool to visualize semiconductor fabrication "
    "steps without TCAD software or a cleanroom. Adjust parameters, preview "
    "the physics, then click **Apply to Wafer** to commit that step onto a "
    "single simulated wafer that carries forward through every tab."
)

# ---------------------------------------------------------------------------
# Sidebar: the running wafer state, visible from every tab.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Current Wafer State")
    st.write(f"**{wafer.diameter_mm}mm {wafer.orientation}**, {wafer.substrate_type}")
    st.write(f"Background doping: {wafer.background_doping_cm3:.2e} cm⁻³")
    st.write(f"Total oxide grown: {wafer.total_oxide_um()*1000:.1f} nm")
    st.write(f"Layers on wafer: {len(wafer.layers)}")
    if wafer.layers:
        for l in wafer.layers:
            st.caption(f"  • {l.name}: {l.thickness_um*1000:.1f} nm")

    st.divider()
    st.subheader("Process History")
    if wafer.history:
        for i, entry in enumerate(wafer.history, 1):
            st.caption(f"{i}. {entry}")
    else:
        st.caption("No steps applied yet — this is a bare wafer.")

    st.divider()
    if st.button("🔄 Reset Wafer (start over)"):
        st.session_state.wafer = WaferState.fresh()
        st.rerun()

tabs = st.tabs([
    "1. Wafer Prep",
    "2. Oxidation",
    "3. Photolithography",
    "4. Ion Implantation",
    "5. Diffusion",
    "6. Deposition",
    "7. Etching",
])

# ---------------------------------------------------------------------------
# 1. WAFER PREPARATION
# ---------------------------------------------------------------------------
with tabs[0]:
    st.header("Wafer Preparation")
    st.markdown(
        """
        Silicon ingots are grown (Czochralski process), sliced into wafers,
        then lapped, etched, and polished to a mirror finish. Key
        specifications include diameter, crystal orientation, resistivity,
        and dopant type (n-type or p-type substrate). **This is the
        foundation every later step builds on** — resistivity here sets
        the background doping that implantation and diffusion will be
        compared against (the "junction depth" line you'll see later).
        """
    )
    col1, col2, col3 = st.columns(3)
    diameter_mm = col1.selectbox("Wafer diameter (mm)", [100, 150, 200, 300], index=2)
    orientation = col2.selectbox("Crystal orientation", ["<100>", "<111>"])
    substrate_type = col3.selectbox("Substrate type", ["p-type (Boron)", "n-type (Phosphorus)"])

    resistivity = st.slider("Substrate resistivity (ohm-cm)", 0.01, 50.0, 10.0)
    st.info(
        f"Preview: {diameter_mm} mm wafer, {orientation} orientation, "
        f"{substrate_type}, {resistivity:.2f} ohm-cm resistivity."
    )
    fig = draw_wafer_stack([], title="Bare Silicon Wafer")
    st.pyplot(fig)

    if st.button("✅ Apply to Wafer", key="apply_prep"):
        step_wafer_prep(wafer, diameter_mm, orientation, substrate_type, resistivity)
        st.success("Wafer prep applied. This sets the background doping used by every later step.")
        st.rerun()

# ---------------------------------------------------------------------------
# 2. THERMAL OXIDATION
# ---------------------------------------------------------------------------
with tabs[1]:
    st.header("Thermal Oxidation (Deal-Grove Model)")
    st.caption(f"Current wafer already has {wafer.total_oxide_um()*1000:.1f} nm of oxide. "
               "A new oxidation step continues growing from that thickness, not from zero.")
    col1, col2 = st.columns(2)
    with col1:
        ox_temp = st.slider("Oxidation temperature (°C)", 800, 1200, 1000)
        ox_ambient = st.radio("Ambient", ["dry", "wet"], horizontal=True)
        ox_time = st.slider("Oxidation time (hours)", 0.1, 10.0, 2.0)

    existing_oxide = wafer.total_oxide_um()
    time_arr = np.linspace(0.01, ox_time, 200)
    thickness_arr = oxidation.oxide_thickness(time_arr, ox_temp, ox_ambient, initial_oxide_um=existing_oxide)
    final_thickness = thickness_arr[-1]
    regime, crossover = oxidation.growth_regime(ox_time, ox_temp, ox_ambient)

    with col2:
        st.metric("Oxide thickness after this step", f"{final_thickness:.4f} um "
                                                       f"({final_thickness*1000:.1f} nm)")
        st.metric("Growth regime at this time", regime.capitalize())
        st.caption(f"Linear→parabolic crossover time ≈ {crossover:.2f} hr")

    fig, ax = plt.subplots()
    ax.plot(time_arr, thickness_arr * 1000, color="tab:blue")
    ax.axhline(existing_oxide * 1000, color="gray", linestyle="--", alpha=0.6,
               label=f"Starting oxide ({existing_oxide*1000:.1f} nm)")
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Oxide thickness (nm)")
    ax.set_title(f"SiO2 growth: {ox_ambient} O2 at {ox_temp} °C")
    ax.legend()
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    preview_layers = [l.to_dict() for l in wafer.layers] + [
        {"name": "SiO2 (preview)", "kind": "oxide", "thickness": final_thickness - existing_oxide}
    ]
    st.pyplot(draw_wafer_stack(preview_layers, title="Wafer After This Oxidation Step (preview)"))

    if st.button("✅ Apply to Wafer", key="apply_ox"):
        step_oxidation(wafer, ox_temp, ox_time, ox_ambient)
        st.success("Oxidation applied and added to the wafer's layer stack.")
        st.rerun()

# ---------------------------------------------------------------------------
# 3. PHOTOLITHOGRAPHY
# ---------------------------------------------------------------------------
with tabs[2]:
    st.header("Photolithography")
    st.caption("Lithography doesn't change the wafer's physical layers in this simulator — "
               "it tells you the smallest feature size achievable, which matters for how "
               "tightly you could mask the implant/etch steps that follow.")
    col1, col2 = st.columns(2)
    with col1:
        wl_label = st.selectbox("Exposure source", list(lithography.WAVELENGTHS_NM.keys()), index=3)
        na = st.slider("Numerical Aperture (NA)", 0.3, 1.35, 0.75, step=0.01)
        k1 = st.slider("Process constant k1", 0.25, 0.8, 0.4, step=0.01)

    wl = lithography.WAVELENGTHS_NM[wl_label]
    res = lithography.resolution_nm(wl, na, k1)
    dof = lithography.depth_of_focus_nm(wl, na)

    with col2:
        st.metric("Minimum resolvable feature (CD)", f"{res:.1f} nm")
        st.metric("Depth of focus", f"{dof:.1f} nm")

    na_range = np.linspace(0.3, 1.35, 100)
    res_range = lithography.resolution_nm(wl, na_range, k1)
    fig, ax = plt.subplots()
    ax.plot(na_range, res_range, color="tab:green")
    ax.axvline(na, color="gray", linestyle="--", alpha=0.6)
    ax.set_xlabel("Numerical Aperture")
    ax.set_ylabel("Resolution (nm)")
    ax.set_title(f"Resolution vs. NA at {wl} nm (k1={k1})")
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    st.caption(
        "Resolution = k1 * λ / NA. Depth of Focus = k2 * λ / NA². "
        "Shrinking λ (e.g., moving to EUV) or increasing NA improves resolution "
        "but shrinks the process window (DoF)."
    )

# ---------------------------------------------------------------------------
# 4. ION IMPLANTATION
# ---------------------------------------------------------------------------
with tabs[3]:
    st.header("Ion Implantation")
    st.caption(f"Current background doping on the wafer: {wafer.background_doping_cm3:.2e} cm⁻³ "
               "(set in Wafer Prep). This implant adds on top of whatever doping is already there.")
    col1, col2 = st.columns(2)
    with col1:
        dopant_i = st.selectbox("Dopant species", list(implantation.IMPLANT_PARAMS.keys()))
        energy = st.slider("Implant energy (keV)", 5, 200, 50)
        dose = st.select_slider(
            "Dose (ions/cm²)",
            options=[1e12, 1e13, 1e14, 1e15, 1e16],
            value=1e14,
            format_func=lambda v: f"{v:.0e}"
        )

    x = wafer.x_um
    profile, Rp, dRp = implantation.implant_profile(x, energy, dose, dopant_i)
    combined_preview = wafer.net_doping_cm3 + profile

    with col2:
        st.metric("Projected range Rp", f"{Rp:.4f} um ({Rp*1000:.1f} nm)")
        st.metric("Straggle ΔRp", f"{dRp:.4f} um ({dRp*1000:.1f} nm)")
        st.metric("Peak concentration (this implant)", f"{profile.max():.2e} cm⁻³")

    fig, ax = plt.subplots()
    ax.plot(x, wafer.net_doping_cm3, color="tab:gray", linestyle="--", alpha=0.6, label="Wafer doping before this step")
    ax.plot(x, combined_preview, color="tab:red", label="After this implant (preview)")
    ax.axvline(Rp, color="gray", linestyle=":", alpha=0.6, label="Rp")
    ax.set_xlabel("Depth (um)")
    ax.set_ylabel("Concentration (cm⁻³)")
    ax.set_yscale("log")
    ax.set_title(f"{dopant_i} implant profile: {energy} keV, {dose:.0e} cm⁻²")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    st.pyplot(fig)

    st.caption(
        "Simplified LSS-type Gaussian approximation for teaching. "
        "For accurate Rp/ΔRp, use SRIM/TRIM Monte-Carlo tables."
    )

    if st.button("✅ Apply to Wafer", key="apply_implant"):
        step_implantation(wafer, dopant_i, energy, dose)
        st.success("Implant applied. Go to Diffusion to see this same dose spread out with heat.")
        st.rerun()

# ---------------------------------------------------------------------------
# 5. DIFFUSION
# ---------------------------------------------------------------------------
with tabs[4]:
    st.header("Dopant Diffusion")
    if wafer.last_implant_dose_cm2:
        st.caption(f"Picking up the {wafer.last_implant_dopant} implant from the previous step "
                   f"(dose {wafer.last_implant_dose_cm2:.1e} cm⁻²). Drive-in mode will spread "
                   "*that same dose* deeper instead of adding a new one.")
    else:
        st.caption("No implant has been applied yet this session — drive-in mode will use a "
                   "default dose. Apply an implant first (tab 4) to diffuse a real dose.")

    diff_mode_label = st.radio("Diffusion type", ["Predeposition (constant source)", "Drive-in (limited source)"],
                                horizontal=True)
    diff_mode = "drive_in" if diff_mode_label.startswith("Drive-in") else "predep"

    col1, col2 = st.columns(2)
    with col1:
        default_dopant = wafer.last_implant_dopant or "Boron"
        dopant_options = list(diffusion.DIFFUSION_PARAMS.keys())
        dopant_d = st.selectbox("Dopant species", dopant_options,
                                 index=dopant_options.index(default_dopant) if default_dopant in dopant_options else 0,
                                 key="diff_dopant")
        diff_temp = st.slider("Diffusion temperature (°C)", 800, 1250, 1050)
        diff_time_min = st.slider("Diffusion time (minutes)", 1, 240, 30)

    x = wafer.x_um
    background = wafer.background_doping_cm3

    if diff_mode == "predep":
        cs = col2.select_slider(
            "Surface concentration Cs (cm⁻³)",
            options=[1e18, 1e19, 1e20, 1e21],
            value=1e20,
            format_func=lambda v: f"{v:.0e}"
        )
        added = diffusion.predeposition_profile(x, diff_time_min * 60, diff_temp, cs, dopant_d)
        preview_profile = wafer.net_doping_cm3 + added
    else:
        dose = wafer.last_implant_dose_cm2 or 1e14
        col2.metric("Dose being driven in", f"{dose:.1e} cm⁻²")
        added = diffusion.drive_in_profile(x, diff_time_min * 60, diff_temp, dose, dopant_d)
        # preview: replace the sharp implant Gaussian with the diffused shape
        implant_shape = (implantation.implant_profile(x, 50, dose, dopant_d)[0]
                          if wafer.last_implant_dose_cm2 else 0)
        preview_profile = np.clip(wafer.net_doping_cm3 - implant_shape, background, None) + added

    xj = diffusion.junction_depth(x, preview_profile, background)
    with col2:
        st.metric("Diffusivity D", f"{diffusion.diffusivity(diff_temp, dopant_d):.2e} cm²/s")
        st.metric("Junction depth (preview)", f"{xj:.3f} um" if xj else "Not reached in range")

    fig, ax = plt.subplots()
    ax.plot(x, wafer.net_doping_cm3, color="tab:gray", linestyle="--", alpha=0.6, label="Wafer doping before this step")
    ax.plot(x, preview_profile, color="tab:purple", label=f"{dopant_d} after diffusion (preview)")
    ax.axhline(background, color="gray", linestyle="--", alpha=0.4, label="Background doping")
    if xj:
        ax.axvline(xj, color="black", linestyle=":", alpha=0.6, label="Junction depth")
    ax.set_xlabel("Depth (um)")
    ax.set_ylabel("Concentration (cm⁻³)")
    ax.set_yscale("log")
    ax.set_title(f"{diff_mode_label} at {diff_temp} °C, {diff_time_min} min")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    st.pyplot(fig)

    if st.button("✅ Apply to Wafer", key="apply_diff"):
        cs_arg = cs if diff_mode == "predep" else None
        step_diffusion(wafer, diff_temp, diff_time_min, diff_mode, dopant=dopant_d, surface_conc_cm3=cs_arg)
        st.success("Diffusion applied. This is now the wafer's permanent doping profile.")
        st.rerun()

# ---------------------------------------------------------------------------
# 6. THIN-FILM DEPOSITION
# ---------------------------------------------------------------------------
with tabs[5]:
    st.header("Thin-Film Deposition")
    st.caption(f"Depositing on top of the current stack ({len(wafer.layers)} layer(s) so far, "
               f"top layer: {wafer.top_layer_name()}).")
    col1, col2 = st.columns(2)
    with col1:
        material = st.selectbox("Material / process", list(deposition.DEPOSITION_PARAMS.keys()))
        needs_temp = deposition.DEPOSITION_PARAMS[material]["R0"] is not None
        dep_temp = st.slider("Deposition temperature (°C)", 200, 800, 600, disabled=not needs_temp)
        dep_time = st.slider("Deposition time (minutes)", 1, 60, 10)

    t_arr = np.linspace(0.1, dep_time, 100)
    thickness_arr = deposition.film_thickness(t_arr, material, dep_temp)
    final_t = thickness_arr[-1]

    with col2:
        st.metric("Deposition rate", f"{deposition.deposition_rate(material, dep_temp):.1f} nm/min")
        st.metric("Final film thickness", f"{final_t:.1f} nm")

    fig, ax = plt.subplots()
    ax.plot(t_arr, thickness_arr, color="tab:orange")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Thickness (nm)")
    ax.set_title(f"{material} deposition")
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    kind = ("polysilicon" if "poly" in material.lower()
            else "nitride" if "nitride" in material.lower()
            else "metal" if "alum" in material.lower()
            else "oxide")
    preview_layers = [l.to_dict() for l in wafer.layers] + [
        {"name": material.split(" (")[0] + " (preview)", "kind": kind, "thickness": final_t / 1000.0}
    ]
    st.pyplot(draw_wafer_stack(preview_layers, title="Wafer After This Deposition (preview)"))

    if st.button("✅ Apply to Wafer", key="apply_dep"):
        step_deposition(wafer, material, dep_temp, dep_time)
        st.success("Deposition applied and added to the wafer's layer stack.")
        st.rerun()

# ---------------------------------------------------------------------------
# 7. ETCHING
# ---------------------------------------------------------------------------
with tabs[6]:
    st.header("Etching")
    st.caption(f"Etching removes material from the top of the current stack "
               f"({len(wafer.layers)} layer(s), top layer: {wafer.top_layer_name()}).")
    col1, col2 = st.columns(2)
    with col1:
        etch_process = st.selectbox("Etch process", list(etching.ETCH_PARAMS.keys()))
        etch_time = st.slider("Etch time (minutes)", 0.1, 20.0, 2.0)
        mask_opening = st.slider("Mask opening width (nm)", 50, 2000, 500)
        mask_thickness = st.slider("Mask thickness (nm)", 50, 1000, 300)

    depth, undercut = etching.etch_profile(etch_time, etch_process, mask_opening)
    remaining_mask = etching.mask_erosion(etch_time, etch_process, mask_thickness)

    with col2:
        st.metric("Vertical etch depth", f"{depth:.1f} nm")
        st.metric("Lateral undercut (per side)", f"{undercut:.1f} nm")
        st.metric("Remaining mask thickness", f"{remaining_mask:.1f} nm")
        total_stack_nm = sum(l.thickness_um for l in wafer.layers) * 1000
        if depth > total_stack_nm:
            st.warning(f"This etch ({depth:.0f}nm) would cut through all "
                      f"{total_stack_nm:.0f}nm of deposited/grown layers and reach bare silicon.")

    fig, ax = plt.subplots(figsize=(6, 3))
    top_width = mask_opening
    trench_x = [0, top_width, top_width - undercut, undercut, 0]
    trench_y = [0, 0, -depth, -depth, 0]
    ax.fill(trench_x, trench_y, color="#a6cee3", edgecolor="black")
    ax.set_xlabel("Width (nm)")
    ax.set_ylabel("Depth (nm)")
    ax.set_title(f"Etch profile: {etch_process}")
    ax.invert_yaxis()
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    st.caption(
        "Anisotropy factor = 1 - (lateral rate / vertical rate). "
        "Wet etches are isotropic (undercut ≈ depth); RIE/DRIE are anisotropic "
        "(mostly vertical walls)."
    )

    if st.button("✅ Apply to Wafer", key="apply_etch"):
        step_etching(wafer, etch_process, etch_time, mask_opening, mask_thickness)
        st.success("Etch applied. Check the sidebar — layers may have been thinned or fully removed.")
        st.rerun()

st.divider()
st.caption(
    "Built with Python, NumPy, SciPy, Matplotlib, and Streamlit. "
    "Models are simplified for education — see README.md for accuracy notes "
    "and links to research-grade open-source TCAD tools."
)