"""
Virtual CMOS Fab - 3D version
=============================
Two modes (left sidebar):
  1. Fabrication flow (3D)  - add steps in order, scrub or play the 3D wafer
  2. Photolithography lab   - its own 9-step sequence, separate from the flow

Run:  pip install streamlit numpy plotly
      streamlit run app3d.py
"""
import time
import numpy as np
import streamlit as st

from modules.wafer3d import (Wafer3D, DOPANTS, DEPOSITION, ETCH_PROCS, ETCH_TARGETS,
                             deal_grove_AB)
from modules import litho_process as lp
from modules.viz3d import wafer_figure, profile_figure, litho_figure

st.set_page_config(page_title="CMOS Fab 3D", layout="wide")


def show(fig, key=None):
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)


# ============================================================ state
if "wafer" not in st.session_state:
    st.session_state.wafer = Wafer3D()
    st.session_state.snaps = [st.session_state.wafer.snapshot()]
    st.session_state.labels = ["Start: bare wafer"]
    st.session_state.view = 0
W: Wafer3D = st.session_state.wafer


def commit(label):
    st.session_state.snaps.append(W.snapshot())
    st.session_state.labels.append(label)
    st.session_state.view = len(st.session_state.snaps) - 1


def reset_all():
    st.session_state.wafer = Wafer3D()
    st.session_state.snaps = [st.session_state.wafer.snapshot()]
    st.session_state.labels = ["Start: bare wafer"]
    st.session_state.view = 0


def run_step(kind, a):
    """Apply one step dict to W (used by the form and by the example flow)."""
    if kind == "Wafer prep":
        W.prep(a["d"], a["o"], a["s"], a["rho"])
    elif kind == "Oxidation":
        W.oxidize(a["T"], a["h"], a["amb"])
    elif kind == "Ion implantation":
        W.implant(a["dop"], a["E"], a["dose"], a["mask"])
    elif kind == "Diffusion / anneal":
        W.diffuse(a["T"], a["min"])
    elif kind == "Deposition":
        W.deposit(a["mat"], a["T"], a["min"])
    elif kind == "Etching":
        W.etch(a["proc"], a["depth"], a["target"], a["mask"], a["stop"])
    commit(W.log[-1])


def inside(x0, x1):
    return dict(mode="inside", x0=x0, x1=x1)


def outside(x0, x1):
    return dict(mode="outside", x0=x0, x1=x1)


EXAMPLE = [
    ("Wafer prep", dict(d=200, o="<100>", s="p-type (Boron)", rho=10.0)),
    ("Oxidation", dict(T=1000, h=0.7, amb="wet")),
    ("Etching", dict(proc="RIE (anisotropic)", depth=450, target="Oxide (SiO2)", mask=inside(1.2, 2.8), stop=True)),
    ("Oxidation", dict(T=950, h=0.4, amb="dry")),
    ("Deposition", dict(mat="Polysilicon (LPCVD)", T=620, min=30)),
    ("Etching", dict(proc="RIE (anisotropic)", depth=350, target="Polysilicon", mask=outside(1.8, 2.2), stop=True)),
    ("Ion implantation", dict(dop="Arsenic", E=80, dose=5e15, mask=None)),
    ("Diffusion / anneal", dict(T=1000, min=20)),
    ("Deposition", dict(mat="SiO2 (CVD)", T=700, min=20)),
    ("Etching", dict(proc="RIE (anisotropic)", depth=560, target="Oxide (SiO2)", mask=inside(1.35, 1.65), stop=True)),
    ("Etching", dict(proc="RIE (anisotropic)", depth=560, target="Oxide (SiO2)", mask=inside(2.35, 2.65), stop=True)),
    ("Deposition", dict(mat="Aluminium (sputter)", T=25, min=5)),
    ("Etching", dict(proc="RIE (anisotropic)", depth=520, target="Metal (Al)", mask=inside(1.8, 2.2), stop=True)),
]
EXAMPLE_NOTES = ["bare p-type wafer", "thick field oxide", "open the active area", "thin gate oxide",
                 "polysilicon film", "pattern the gate", "self-aligned source/drain implant",
                 "anneal the dopants", "insulating oxide", "contact hole 1", "contact hole 2",
                 "metal film", "split metal into source/drain pads"]

# ============================================================ sidebar
mode = st.sidebar.radio("Mode", ["Fabrication flow (3D)", "Photolithography lab"])
st.sidebar.divider()
st.sidebar.caption("Photolithography is a separate lab with its own 9 sub-steps. "
                   "In the fab flow, the 'Resist mask' option stands in for the pattern it makes.")

# ============================================================ MODE 1: FAB FLOW
if mode == "Fabrication flow (3D)":
    st.title("Virtual CMOS Fab - 3D")
    left, right = st.columns([1, 2.2], gap="large")

    with left:
        st.subheader("Add the next step")
        kind = st.selectbox("Step", ["Wafer prep", "Oxidation", "Ion implantation",
                                     "Diffusion / anneal", "Deposition", "Etching"])
        a = {}
        use_mask = False
        if kind == "Wafer prep":
            a["d"] = st.selectbox("Diameter (mm)", [100, 150, 200, 300], index=2)
            a["o"] = st.selectbox("Orientation", ["<100>", "<111>"])
            a["s"] = st.selectbox("Substrate", ["p-type (Boron)", "n-type (Phosphorus)"])
            a["rho"] = st.slider("Resistivity (ohm-cm)", 0.5, 50.0, 10.0)
            st.caption("Prep resets the wafer.")
        elif kind == "Oxidation":
            a["T"] = st.slider("Temperature (C)", 800, 1200, 1000)
            a["amb"] = st.radio("Ambient", ["dry", "wet"], horizontal=True)
            a["h"] = st.slider("Time (hours)", 0.1, 5.0, 0.7, 0.1)
            A, B = deal_grove_AB(a["T"], a["amb"])
            x1 = (A / 2) * (np.sqrt(1 + a["h"] / (A * A / (4 * B))) - 1)
            st.caption(f"Bare-silicon estimate: about {x1*1000:.0f} nm of oxide. "
                       "Grows only where there is no poly/nitride/metal on top.")
        elif kind == "Ion implantation":
            a["dop"] = st.selectbox("Dopant", list(DOPANTS))
            a["E"] = st.slider("Energy (keV)", 10, 200, 80)
            a["dose"] = st.select_slider("Dose (cm-2)", [1e12, 1e13, 1e14, 1e15, 5e15, 1e16], value=5e15,
                                         format_func=lambda v: f"{v:.0e}")
            use_mask = True
            st.caption("Films already on the wafer stop the ions, so a poly gate protects what is under it (self-alignment).")
        elif kind == "Diffusion / anneal":
            a["T"] = st.slider("Temperature (C)", 800, 1250, 1000)
            a["min"] = st.slider("Time (minutes)", 1, 240, 20)
            st.caption("Spreads existing dopants down AND sideways.")
        elif kind == "Deposition":
            a["mat"] = st.selectbox("Material", list(DEPOSITION))
            a["T"] = st.slider("Temperature (C)", 25, 800, DEPOSITION[a["mat"]][2])
            a["min"] = st.slider("Time (minutes)", 1, 60, 30 if "Poly" in a["mat"] else 20)
            st.caption("Conformal: coats everything on the wafer evenly.")
        else:
            a["proc"] = st.selectbox("Etch process", list(ETCH_PROCS))
            a["target"] = st.selectbox("Etch which material?", list(ETCH_TARGETS))
            a["depth"] = st.slider("Etch depth (nm)", 10, 1000, 350, 10)
            a["stop"] = st.checkbox("Stop at silicon", value=True)
            use_mask = True
            st.caption("Selective etches stop on other materials, e.g. poly etch stops on gate oxide.")
        if use_mask:
            mm = st.radio("Resist mask (from the litho lab)", ["none", "open inside window", "open outside window"],
                          horizontal=False, key=f"mm_{kind}")
            x0, x1 = st.slider("Window x-range (um)", 0.0, 4.0, (1.2, 2.8), 0.05, key=f"win_{kind}")
            a["mask"] = None if mm == "none" else dict(
                mode="inside" if "inside" in mm else "outside", x0=x0, x1=x1)
        if st.button("Add step", type="primary"):
            run_step(kind, a)
            st.rerun()

        c1, c2 = st.columns(2)
        if c1.button("Load example CMOS flow"):
            reset_all()
            for (k, args), _n in zip(EXAMPLE, EXAMPLE_NOTES):
                run_step(k, args)
            st.rerun()
        if c2.button("Reset"):
            reset_all()
            st.rerun()

    with right:
        n = len(st.session_state.snaps)
        view_ph = st.empty()
        if n > 1:
            st.session_state.view = min(st.session_state.view, n - 1)
            st.slider("Step shown (scrub through the process)", 0, n - 1, key="view")
            play = st.button("Play process")
        else:
            play = False
            st.info("No steps yet. Add one on the left, or load the example flow.")

        def draw(i):
            snap = st.session_state.snaps[i]
            with view_ph.container():
                st.caption(f"Step {i}/{n-1}: {st.session_state.labels[i]}")
                show(wafer_figure(snap, f"After step {i}"), key=f"fig_{i}_{time.time_ns()}")

        if play:
            for i in range(n):
                draw(i)
                time.sleep(1.0)
            st.session_state.view = n - 1
        else:
            draw(st.session_state.view)

        snap = st.session_state.snaps[st.session_state.view]
        t1, t2 = st.columns([1, 1])
        with t1:
            xsel = st.slider("Doping profile at x (um)", 0.0, 4.0, 1.5, 0.05)
            show(profile_figure(snap, xsel), key="prof")
        with t2:
            st.markdown("**Process history**")
            for i, lab in enumerate(st.session_state.labels):
                st.write(("**-> " if i == st.session_state.view else "") + f"{i}. {lab}"
                         + ("**" if i == st.session_state.view else ""))
            if snap.layers:
                st.markdown("**Layers at x = 2 um**")
                ix = int(2.0 / snap.dx)
                for l in snap.layers:
                    st.caption(f"{l['name']}: {l['t'][ix]*1000:.0f} nm")

# ============================================================ MODE 2: LITHO LAB
else:
    st.title("Photolithography lab")
    st.caption("A self-contained 9-step sequence. Change settings on the left, then step through "
               "the process and watch the resist change. Each step explains itself.")
    pc, vc = st.columns([1, 2.2], gap="large")
    with pc:
        with st.expander("1-2  Surface prep", expanded=False):
            clean_T = st.slider("Dehydration bake (C)", 80, 200, 150)
            clean_min = st.slider("Bake time (min)", 1, 10, 5)
            hmds_s = st.slider("HMDS vapour time (s)", 0, 90, 30)
        with st.expander("3-4  Resist coat & soft bake", expanded=False):
            rpm = st.slider("Spin speed (rpm)", 1000, 6000, 4000, 100)
            visc = st.selectbox("Resist viscosity", ["low", "medium", "high"], index=1)
            soft_T = st.slider("Soft bake (C)", 70, 150, 100)
            soft_s = st.slider("Soft bake time (s)", 10, 120, 60)
        with st.expander("5-6  Align & expose", expanded=True):
            cd = st.slider("Target line width, CD (nm)", 150, 1500, 600, 10)
            wl_name = st.selectbox("Light source", list(lp.WAVELENGTHS), index=1)
            na = st.slider("Numerical aperture (NA)", 0.2, 0.9, 0.5, 0.01)
            dose = st.slider("Dose (mJ/cm2)", 20, 400, 150, 5)
            defocus = st.slider("Defocus (nm)", -1500, 1500, 0, 50)
            overlay = st.slider("Alignment error (nm)", 0, 300, 0, 10)
        with st.expander("7-9  PEB, develop, hard bake", expanded=False):
            peb_T = st.slider("PEB (C)", 80, 140, 110)
            peb_s = st.slider("PEB time (s)", 10, 120, 60)
            tone = st.radio("Resist tone", ["positive", "negative"], horizontal=True)
            dev_s = st.slider("Develop time (s)", 10, 150, 60)
            hard_T = st.slider("Hard bake (C)", 90, 180, 120)
            hard_s = st.slider("Hard bake time (s)", 30, 300, 120)

    params = lp.LithoParams(clean_T, clean_min, hmds_s, rpm, visc, soft_T, soft_s, overlay,
                            lp.WAVELENGTHS[wl_name], na, dose, defocus, cd, peb_T, peb_s, tone,
                            dev_s, hard_T, hard_s)
    states = lp.run(params)
    with vc:
        if "litho_i" not in st.session_state:
            st.session_state.litho_i = 0
        st.slider("Sub-step", 0, 8, key="litho_i",
                  format="Step %d")
        ph = st.empty()
        if st.button("Play all 9 steps"):
            for i, s in enumerate(states):
                with ph.container():
                    st.markdown(f"### {s['step']}")
                    st.write(s["what"])
                    show(litho_figure(s, i), key=f"lp_{i}_{time.time_ns()}")
                time.sleep(1.3)
            st.session_state.litho_i = 8
        else:
            i = st.session_state.litho_i
            s = states[i]
            with ph.container():
                st.markdown(f"### {s['step']}")
                st.write(s["what"])
                show(litho_figure(s, i), key=f"lp_{i}")
                if s["metrics"]:
                    cols = st.columns(len(s["metrics"]))
                    for c, (k, v) in zip(cols, s["metrics"].items()):
                        c.metric(k, v)
                for wmsg in s["warnings"]:
                    st.warning(wmsg)
