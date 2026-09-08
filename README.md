# Virtual CMOS Fabrication Process Simulator

An interactive, open-source Python tool for visualizing the major steps of
CMOS semiconductor fabrication — wafer prep, thermal oxidation,
photolithography, ion implantation, diffusion, thin-film deposition, and
etching — without needing TCAD software or a cleanroom.

Built with **NumPy**, **SciPy**, **Matplotlib**, and **Streamlit**.

## Features (v0.1 — starter version)

- Interactive sliders for temperature, time, dopant, energy, dose, NA, etc.
- Real physics models per step:
  - **Oxidation** — Deal-Grove model (linear + parabolic regimes, dry/wet)
  - **Photolithography** — Rayleigh resolution & depth-of-focus
  - **Ion Implantation** — Gaussian projected-range profile
  - **Diffusion** — erfc (predeposition) and Gaussian (drive-in) profiles,
    with junction-depth extraction
  - **Deposition** — Arrhenius growth-rate model for CVD films
  - **Etching** — isotropic vs. anisotropic depth/undercut and mask erosion
- Live graphs (concentration profiles, thickness vs. time, resolution vs. NA)
- Simple wafer cross-section illustrations after each step

## Project Structure

```
cmos_simulator/
├── app.py                  # Streamlit UI, ties all modules together
├── requirements.txt
└── modules/
    ├── oxidation.py         # Deal-Grove thermal oxidation
    ├── lithography.py       # Rayleigh resolution / DoF
    ├── implantation.py      # Gaussian ion implant profile
    ├── diffusion.py         # erfc / Gaussian diffusion profiles
    ├── deposition.py        # Arrhenius CVD film growth
    ├── etching.py            # isotropic / anisotropic etch models
    └── wafer_view.py         # matplotlib wafer cross-section illustrator
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

This opens the app in your browser at `http://localhost:8501`.

## Accuracy Notes (read before citing results)

This is a **teaching tool**, not a production TCAD simulator:

- Rate constants (oxidation, diffusion, deposition) use standard textbook
  Arrhenius parameters for common conditions — real fabs calibrate these
  per-tool and per-recipe.
- Ion implant Rp/ΔRp use a simplified power-law fit, not SRIM/TRIM
  Monte-Carlo data.
- Etch and lithography models are first-order (Rayleigh criterion,
  constant-rate etch) and ignore effects like proximity, loading, or
  RET (OPC, phase-shift masks).
- The wafer cross-section is a schematic illustration, not a meshed 2D/3D
  topography simulation.

## Ideas for Extending This Project

- Add a full process **flow builder** (chain steps in sequence, carry the
  wafer state — oxide thickness, doping profile — from one tab to the next)
- Replace the implant model with real SRIM output or a lookup table
- Add CMP (chemical-mechanical planarization) and silicidation steps
- 2D/3D cross-section rendering (e.g., with a level-set method) for
  realistic topography instead of flat layers
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
  starter project, but heavier to set up (C++ core).

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

This starter project is intended for educational use — adapt freely for
coursework or further development.
