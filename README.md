# Virtual CMOS Fabrication Process Simulator

An interactive, open-source Python tool for visualizing the major steps of
CMOS semiconductor fabrication — wafer prep, thermal oxidation,
photolithography, ion implantation, diffusion, thin-film deposition, and
etching — without needing TCAD software or a cleanroom.

Built with **NumPy**, **SciPy**, **Matplotlib**, **Plotly**, and **Streamlit**.

The project ships as **two apps** that you can run separately:

| App | Command | What it is |
|---|---|---|
| `app.py` | `streamlit run app.py` | 2D version: 7 tabs, one shared wafer state, "Apply to Wafer" chaining |
| `app3d.py` | `streamlit run app3d.py` | 3D version: sequential flow builder with a 3D wafer, plus a separate photolithography lab |

## Features (v0.2)

### 2D app (`app.py`)
- Interactive sliders for temperature, time, dopant, energy, dose, NA, etc.
- Real physics models per step:
  - **Oxidation** — Deal-Grove model (linear + parabolic regimes, dry/wet)
  - **Photolithography** — Rayleigh resolution & depth-of-focus
  - **Ion Implantation** — Gaussian projected-range profile
  - **Diffusion** — erfc (predeposition) and Gaussian (drive-in) profiles,
    with junction-depth extraction
  - **Deposition** — Arrhenius growth-rate model for CVD films
  - **Etching** — isotropic vs. anisotropic depth/undercut and mask erosion
- **Persistent wafer state** (`wafer_state.py`): each tab's *Apply to Wafer*
  button commits that step, so oxide thickness, doping and layers carry
  forward through the whole run. The sidebar shows the live state and history.
- Live graphs and simple wafer cross-section illustrations

### 3D app (`app3d.py`)
- **Fabrication flow (3D)**
  - Add steps in order (prep, oxidation, implant, diffusion, deposition, etch).
    Every step changes the same wafer.
  - Scrub through the steps with a slider, or press **Play process** to
    animate the whole flow.
  - The wafer is a 2D cross-section extruded into 3D. The cut face is coloured
    by net doping (red = p-type, blue = n-type) so junctions are visible.
  - A doping-vs-depth plot at any lateral position, with junction depth marked.
  - Films stop implanted ions, so a poly gate protects the silicon under it
    (self-aligned source/drain).
  - Diffusion spreads dopants sideways as well as downward.
  - Etches can target a single material (oxide, poly, nitride, metal, silicon)
    and stop on the layer below.
  - **Load example CMOS flow** builds a small transistor in 13 steps
    (field oxide, gate oxide, poly gate, S/D implant, anneal, ILD, contacts, metal).
- **Photolithography lab** — its own 9-step sequence, separate from the fab flow:
  1. Clean & dehydration bake
  2. HMDS adhesion primer
  3. Spin-coat photoresist
  4. Soft bake
  5. Mask alignment
  6. Exposure (3D scene shows mask and UV)
  7. Post-exposure bake
  8. Develop
  9. Hard bake & inspect

  Each sub-step has a plain-language explanation, measured values (thickness,
  contrast, printed line width, sidewall angle) and warnings for bad settings.
- Lithography is **not** chained into the flow. In the fab flow, the
  *Resist mask* option (open inside/outside a window) stands in for the
  pattern the lab produces.

## Project Structure

```
cmos_simulator/
├── app.py                  # 2D Streamlit UI (7 tabs, shared wafer state)
├── app3d.py                # 3D Streamlit UI (flow builder + litho lab)
├── requirements.txt
└── modules/
    ├── oxidation.py         # Deal-Grove thermal oxidation
    ├── lithography.py       # Rayleigh resolution / DoF
    ├── implantation.py      # Gaussian ion implant profile
    ├── diffusion.py         # erfc / Gaussian diffusion profiles
    ├── deposition.py        # Arrhenius CVD film growth
    ├── etching.py           # isotropic / anisotropic etch models
    ├── wafer_view.py        # matplotlib wafer cross-section illustrator
    ├── wafer_state.py       # shared wafer state used by app.py
    ├── wafer3d.py           # 2D cross-section wafer model used by app3d.py
    ├── litho_process.py     # 9-step photolithography lab model
    └── viz3d.py             # Plotly 3D scenes
```

`app3d.py` and its three modules (`wafer3d.py`, `litho_process.py`, `viz3d.py`)
are self-contained and do not import the older modules, so the two apps
cannot break each other.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py            # 2D version
streamlit run app3d.py          # 3D version
```

This opens the app in your browser at `http://localhost:8501`.
Make sure `requirements.txt` includes `plotly` (needed by `app3d.py`).

## Accuracy Notes (read before citing results)

This is a **teaching tool**, not a production TCAD simulator:

- Rate constants (oxidation, diffusion, deposition) use standard textbook
  Arrhenius parameters for common conditions — real fabs calibrate these
  per-tool and per-recipe.
- Ion implant Rp/ΔRp use a simplified power-law fit, not SRIM/TRIM
  Monte-Carlo data. In the 3D app, films above the silicon are assumed to
  stop ions like silicon does.
- Etch and lithography models are first-order (Rayleigh criterion,
  constant-rate etch, simplified aerial-image contrast and resist response)
  and ignore effects like proximity, loading, or RET (OPC, phase-shift masks).
- The 2D app's wafer cross-section is a schematic illustration. The 3D app
  uses a coarse 2D grid (about 40 nm lateral, 20 nm vertical) extruded into
  3D, so features smaller than a grid cell are not resolved. Deposition is
  perfectly conformal, and etch undercut is a simple rounded profile, not a
  level-set simulation.
- Thermal oxide consumes silicon (44% of its thickness) and grows only where
  no poly, nitride or metal covers the surface.

## Ideas for Extending This Project

- ~~Process flow builder with persistent wafer state~~ (done: `wafer_state.py`, `wafer3d.py`)
- ~~2D/3D cross-section rendering~~ (done in a simplified form: `viz3d.py`)
- Feed the litho lab's printed pattern directly into the flow as the mask
- Replace the implant model with real SRIM output or a lookup table
- Add CMP (chemical-mechanical planarization) and silicidation steps
- True topography with a level-set method (e.g. ViennaPS) instead of columns
- Export process recipes / results to CSV or PDF reports
- Add a MOSFET I-V calculator once doping profiles are generated, to close
  the loop from process → device

## Learning Resources

### Textbooks & Theory
- *Silicon VLSI Technology* — Plummer, Deal, Griffin (the canonical source
  for the Deal-Grove and diffusion models used in this project)
- *Semiconductor process simulation* — [Wikipedia overview](https://en.wikipedia.org/wiki/Semiconductor_process_simulation) of TCAD process
  steps and the standard models (Deal-Grove, LSS, Fick's laws)
- [Deal-Grove model — Wikipedia](https://en.wikipedia.org/wiki/Deal%E2%80%93Grove_model)

### Free / Browser-Based Simulation Platforms
- [nanoHUB.org](https://nanohub.org) — Purdue-hosted platform with 80+ free,
  browser-based semiconductor simulation tools, including an interactive
  **oxidation** tool (Deal-Grove + Massoud model) and **ion implantation**
  tools. No install required. Search "Explore → Tools" for topics like
  oxidation, diffusion, ion implantation, MOSFET.
- nanoHUB Semiconductor Device Physics group: https://nanohub.org/groups/semiconductors/semiconductortools

### Open-Source TCAD / Process Simulation Code (for going further)
- [DEVSIM](https://github.com/devsim/devsim) — Apache-2.0 licensed, Python-scriptable
  TCAD **device** simulator (drift-diffusion). Good next step after this
  project if you want to simulate device I-V from a doping profile.
- [ViennaPS](https://github.com/ViennaTools/ViennaPS) — open-source **topography/process**
  simulation library (etching, deposition, oxidation) using level-set
  methods, with Python bindings. Much closer to real TCAD than this
  project, but heavier to set up (C++ core).

### Reference Data / Circuit-Level Tools
- [Predictive Technology Model (PTM)](https://ptm.asu.edu/) — free, downloadable
  SPICE-compatible transistor model files for various process nodes, useful
  once you want to go from "process" to "circuit."
- [ngspice](https://ngspice.sourceforge.io/) — free SPICE circuit simulator, useful for
  simulating the CMOS logic gates fabricated by your virtual process.

### Papers
- Deal, B.E. and Grove, A.S., "General Relationship for the Thermal
  Oxidation of Silicon," *J. Appl. Phys.* 36, 3770 (1965) — the original
  Deal-Grove paper.
- Tasch, A.F., Shin, H., Park, C., "An Improved Approach to Accurately
  Model Shallow B and BF2 Implants in Silicon," *J. Electrochem. Soc.*
  136(3), 810 (1989) — background on Gaussian/Pearson-IV implant profile
  fitting, useful if you extend the implantation module.

## License

This project is intended for educational use — adapt freely for
coursework or further development.
