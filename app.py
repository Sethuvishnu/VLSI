"""
Virtual CMOS Fabrication Process Simulator
=============================================
An interactive, educational Python/Streamlit app that walks through the
major steps of CMOS fabrication:

    1. Wafer Preparation
    2. Thermal Oxidation      (Deal-Grove model)
    3. Photolithography       (Rayleigh resolution / DoF)
    4. Ion Implantation       (Gaussian profile)
    5. Diffusion              (predeposition / drive-in)
    6. Thin-Film Deposition   (Arrhenius growth rate)
    7. Etching                (isotropic vs anisotropic)

Run with:
    pip install -r requirements.txt
    streamlit run app.py
"""

import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from modules import oxidation, diffusion, implantation, deposition, etching, lithography
from modules.wafer_view import draw_wafer_stack

st.set_page_config(page_title="CMOS Fabrication Simulator", layout="wide")

st.title("🔬 Virtual CMOS Fabrication Process Simulator")
st.caption(
    "An educational, open-source tool to visualize semiconductor fabrication "
    "steps without TCAD software or a cleanroom. Adjust parameters in each "
    "tab and see the physics respond in real time."
)

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
        and dopant type (n-type or p-type substrate).
        """
    )
    col1, col2, col3 = st.columns(3)
    diameter_mm = col1.selectbox("Wafer diameter (mm)", [100, 150, 200, 300], index=2)
    orientation = col2.selectbox("Crystal orientation", ["<100>", "<111>"])
    substrate_type = col3.selectbox("Substrate type", ["p-type (Boron)", "n-type (Phosphorus)"])

    resistivity = st.slider("Substrate resistivity (ohm-cm)", 0.01, 50.0, 10.0)
    st.info(
        f"Selected: {diameter_mm} mm wafer, {orientation} orientation, "
        f"{substrate_type}, {resistivity:.2f} ohm-cm resistivity."
    )
    fig = draw_wafer_stack([], title="Bare Silicon Wafer")
    st.pyplot(fig)

# ---------------------------------------------------------------------------
# 2. THERMAL OXIDATION
# ---------------------------------------------------------------------------
with tabs[1]:
    st.header("Thermal Oxidation (Deal-Grove Model)")
    col1, col2 = st.columns(2)
    with col1:
        ox_temp = st.slider("Oxidation temperature (°C)", 800, 1200, 1000)
        ox_ambient = st.radio("Ambient", ["dry", "wet"], horizontal=True)
        ox_time = st.slider("Oxidation time (hours)", 0.1, 10.0, 2.0)

    time_arr = np.linspace(0.01, ox_time, 200)
    thickness_arr = oxidation.oxide_thickness(time_arr, ox_temp, ox_ambient)
    final_thickness = thickness_arr[-1]
    regime, crossover = oxidation.growth_regime(ox_time, ox_temp, ox_ambient)

    with col2:
        st.metric("Final oxide thickness", f"{final_thickness:.4f} um "
                                             f"({final_thickness*1000:.1f} nm)")
        st.metric("Growth regime at this time", regime.capitalize())
        st.caption(f"Linear→parabolic crossover time ≈ {crossover:.2f} hr")

    fig, ax = plt.subplots()
    ax.plot(time_arr, thickness_arr * 1000, color="tab:blue")
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Oxide thickness (nm)")
    ax.set_title(f"SiO2 growth: {ox_ambient} O2 at {ox_temp} °C")
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    st.pyplot(draw_wafer_stack(
        [{"name": "SiO2", "kind": "oxide", "thickness": final_thickness}],
        title="Wafer After Oxidation"
    ))

# ---------------------------------------------------------------------------
# 3. PHOTOLITHOGRAPHY
# ---------------------------------------------------------------------------
with tabs[2]:
    st.header("Photolithography")
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

    x = np.linspace(0, 0.6, 400)  # depth in um
    profile, Rp, dRp = implantation.implant_profile(x, energy, dose, dopant_i)

    with col2:
        st.metric("Projected range Rp", f"{Rp:.4f} um ({Rp*1000:.1f} nm)")
        st.metric("Straggle ΔRp", f"{dRp:.4f} um ({dRp*1000:.1f} nm)")
        st.metric("Peak concentration", f"{profile.max():.2e} cm⁻³")

    fig, ax = plt.subplots()
    ax.plot(x, profile, color="tab:red")
    ax.axvline(Rp, color="gray", linestyle="--", alpha=0.6, label="Rp")
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

# ---------------------------------------------------------------------------
# 5. DIFFUSION
# ---------------------------------------------------------------------------
with tabs[4]:
    st.header("Dopant Diffusion")
    diff_mode = st.radio("Diffusion type", ["Predeposition (constant source)", "Drive-in (limited source)"],
                          horizontal=True)
    col1, col2 = st.columns(2)
    with col1:
        dopant_d = st.selectbox("Dopant species", list(diffusion.DIFFUSION_PARAMS.keys()), key="diff_dopant")
        diff_temp = st.slider("Diffusion temperature (°C)", 800, 1250, 1050)
        diff_time_min = st.slider("Diffusion time (minutes)", 1, 240, 30)

    x = np.linspace(0, 3, 400)  # depth in um
    background = 1e15  # substrate doping, cm^-3

    if diff_mode.startswith("Predeposition"):
        cs = col2.select_slider(
            "Surface concentration Cs (cm⁻³)",
            options=[1e18, 1e19, 1e20, 1e21],
            value=1e20,
            format_func=lambda v: f"{v:.0e}"
        )
        profile = diffusion.predeposition_profile(x, diff_time_min * 60, diff_temp, cs, dopant_d)
    else:
        dose = col2.select_slider(
            "Total dose Q (cm⁻²)",
            options=[1e13, 1e14, 1e15],
            value=1e14,
            format_func=lambda v: f"{v:.0e}"
        )
        profile = diffusion.drive_in_profile(x, diff_time_min * 60, diff_temp, dose, dopant_d)

    xj = diffusion.junction_depth(x, profile, background)
    with col2:
        st.metric("Diffusivity D", f"{diffusion.diffusivity(diff_temp, dopant_d):.2e} cm²/s")
        st.metric("Junction depth", f"{xj:.3f} um" if xj else "Not reached in range")

    fig, ax = plt.subplots()
    ax.plot(x, profile, color="tab:purple", label=f"{dopant_d} profile")
    ax.axhline(background, color="gray", linestyle="--", alpha=0.6, label="Background doping")
    if xj:
        ax.axvline(xj, color="black", linestyle=":", alpha=0.6, label="Junction depth")
    ax.set_xlabel("Depth (um)")
    ax.set_ylabel("Concentration (cm⁻³)")
    ax.set_yscale("log")
    ax.set_title(f"{diff_mode} at {diff_temp} °C, {diff_time_min} min")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    st.pyplot(fig)

# ---------------------------------------------------------------------------
# 6. THIN-FILM DEPOSITION
# ---------------------------------------------------------------------------
with tabs[5]:
    st.header("Thin-Film Deposition")
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

    st.pyplot(draw_wafer_stack(
        [{"name": material.split(" (")[0], "kind": "polysilicon" if "poly" in material.lower()
          else ("nitride" if "nitride" in material.lower() else ("metal" if "alum" in material.lower() else "oxide")),
          "thickness": final_t / 1000.0}],
        title="Wafer After Deposition"
    ))

# ---------------------------------------------------------------------------
# 7. ETCHING
# ---------------------------------------------------------------------------
with tabs[6]:
    st.header("Etching")
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

    # simple trench cross-section illustration
    fig, ax = plt.subplots(figsize=(6, 3))
    top_width = mask_opening
    bottom_width = max(10, mask_opening - 2 * undercut)
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

st.divider()
st.caption(
    "Built with Python, NumPy, SciPy, Matplotlib, and Streamlit. "
    "Models are simplified for education — see README.md for accuracy notes "
    "and links to research-grade open-source TCAD tools."
)
