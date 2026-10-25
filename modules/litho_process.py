"""
litho_process.py - the photolithography lab: its OWN 9-step sequence,
separate from the main fab flow. Every sub-step returns a state dict that
viz3d.litho_figure() can draw.
"""
from dataclasses import dataclass
import numpy as np

STEP_NAMES = [
    "1. Clean & dehydration bake",
    "2. HMDS adhesion primer",
    "3. Spin-coat photoresist",
    "4. Soft bake",
    "5. Mask alignment",
    "6. Exposure",
    "7. Post-exposure bake (PEB)",
    "8. Develop",
    "9. Hard bake & inspect",
]
WAVELENGTHS = {"g-line 436 nm": 436, "i-line 365 nm": 365, "KrF 248 nm": 248, "ArF 193 nm": 193}
E_ONSET = {436: 80.0, 365: 100.0, 248: 25.0, 193: 20.0}     # mJ/cm2, resist-dependent
GAMMA = 3.0
VISCOSITY = {"low": 0.6, "medium": 1.0, "high": 1.6}
NPTS = 360
PERIODS = 3


@dataclass
class LithoParams:
    clean_T: float = 150.0
    clean_min: float = 5.0
    hmds_s: float = 30.0
    rpm: float = 4000.0
    viscosity: str = "medium"
    soft_T: float = 100.0
    soft_s: float = 60.0
    overlay_nm: float = 0.0
    wavelength_nm: int = 365
    NA: float = 0.5
    dose: float = 150.0
    defocus_nm: float = 0.0
    cd_nm: float = 600.0
    peb_T: float = 110.0
    peb_s: float = 60.0
    tone: str = "positive"
    dev_s: float = 60.0
    hard_T: float = 120.0
    hard_s: float = 120.0


def _blur(a, sigma_px):
    if sigma_px < 0.3:
        return a
    r = int(np.ceil(4 * sigma_px))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_px) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(a, r, mode="wrap"), k, mode="valid")


def _measure(h, x_nm, hmax):
    """Mean width (nm) of resist lines at half height + steepest sidewall angle."""
    on = h > 0.5 * hmax
    edges = np.diff(on.astype(int))
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0]
    widths = []
    for s in starts:
        e = ends[ends > s]
        if len(e):
            widths.append(x_nm[e[0]] - x_nm[s])
    cd = float(np.mean(widths)) if widths else 0.0
    slope = np.max(np.abs(np.gradient(h, x_nm)))
    return cd, float(np.degrees(np.arctan(slope)))


def run(p: LithoParams):
    pitch = 2.0 * p.cd_nm
    L = PERIODS * pitch
    x = np.linspace(0, L, NPTS, endpoint=False)
    dxn = x[1] - x[0]
    states, warn = [], []

    def add(i, what, **kw):
        s = dict(step=STEP_NAMES[i], what=what, film=None, latent=None, hmds=0.0,
                 moisture=None, metrics={}, warnings=[], x_nm=x, pitch=pitch, tone=p.tone)
        s.update(kw)
        states.append(s)
        return s

    # 1 clean + dehydration bake
    tau = 60.0 * np.exp(-(p.clean_T - 100.0) / 30.0)
    moist = float(np.exp(-p.clean_min * 60.0 / tau))
    s = add(0, "Wafer is rinsed, then baked hot to boil off water molecules stuck to the surface. "
               "Water on the surface makes resist peel off later.",
            moisture=moist, metrics={"Surface moisture left": f"{moist*100:.0f} %"})
    if moist > 0.3:
        s["warnings"].append("Still wet: raise the bake temperature or time.")

    # 2 HMDS
    cover = float((1 - 0.7 * moist) * (1 - np.exp(-p.hmds_s / 15.0)))
    adh = 0.2 + 0.8 * cover
    s = add(1, "A thin chemical primer (HMDS) is vapour-coated on. It works like double-sided tape "
               "between silicon and resist.",
            moisture=moist, hmds=cover,
            metrics={"HMDS coverage": f"{cover*100:.0f} %", "Adhesion quality": f"{adh*100:.0f} %"})
    if adh < 0.6:
        s["warnings"].append("Weak adhesion: thin resist lines may lift off in develop.")

    # 3 spin coat
    t0 = 63.0 / np.sqrt(p.rpm) * VISCOSITY[p.viscosity] * 1000.0     # nm
    film = np.full(NPTS, t0)
    add(2, "A puddle of liquid resist is dropped on the centre and the wafer is spun fast. "
           "Faster spin = thinner film (thickness ~ 1/sqrt(rpm)).",
        moisture=moist, hmds=cover, film=film,
        metrics={"Resist thickness": f"{t0:.0f} nm"})

    # 4 soft bake
    tau_s = 30.0 * np.exp(-(p.soft_T - 90.0) / 25.0)
    solvent = float(np.exp(-p.soft_s / tau_s))
    t1 = t0 * (1 - 0.10 * (1 - solvent))
    e0 = E_ONSET[p.wavelength_nm]
    if p.soft_T > 130:
        e0 *= 1.3
    film = np.full(NPTS, t1)
    s = add(3, "A gentle bake drives out the solvent so the resist turns from wet goo into a firm film.",
            moisture=moist, hmds=cover, film=film,
            metrics={"Solvent left": f"{solvent*100:.0f} %", "Film thickness": f"{t1:.0f} nm"})
    if solvent > 0.3:
        s["warnings"].append("Under-baked: film is still soft and will develop unevenly.")
    if p.soft_T > 130:
        s["warnings"].append("Over-baked: the light-sensitive compound is damaged; needs more dose.")

    # 5 alignment
    add(4, "The mask is lined up with marks already printed on the wafer. Any error here "
           "shifts the whole pattern (overlay error).",
        moisture=moist, hmds=cover, film=film,
        metrics={"Overlay error": f"{p.overlay_nm:.0f} nm"})

    # 6 exposure
    lam, NA = p.wavelength_nm, p.NA
    cd_min = 0.31 * lam / NA
    dof = 0.5 * lam / NA ** 2
    fc = 1.6 * NA / lam                       # partially-coherent cutoff (1/nm)
    u = (1.0 / pitch) / fc
    M = max(0.0, 1 - u ** 2)
    M *= float(np.exp(-0.5 * (p.defocus_nm / dof) ** 2))
    xs = x - p.overlay_nm
    # dark line centred in each period, bright space between lines
    E = p.dose * (1 + M * np.cos(2 * np.pi * (xs) / pitch))        # bright at x=0 (space), dark at pitch/2 (line)
    s = add(5, "UV light shines through the mask. Where light lands, the resist chemistry changes "
               "(a hidden 'latent image'). Blurry optics = lower contrast.",
            moisture=moist, hmds=cover, film=film, latent=E,
            metrics={"Image contrast": f"{M*100:.0f} %", "Smallest printable CD (Rayleigh)": f"{cd_min:.0f} nm",
                     "Depth of focus": f"{dof:.0f} nm", "Target CD": f"{p.cd_nm:.0f} nm"})
    s["e0"], s["mask_blocks"] = e0, True
    if p.cd_nm < cd_min:
        s["warnings"].append("Target CD is below the optics' limit: image washes out. "
                             "Use a shorter wavelength or higher NA.")
    if abs(p.defocus_nm) > dof / 2:
        s["warnings"].append("Defocus is large compared to the depth of focus: contrast drops.")

    # 7 PEB
    sig = 8.0 * np.sqrt(p.peb_s / 60.0) * np.exp((p.peb_T - 110.0) / 35.0)
    Eb = _blur(E, sig / dxn)
    Mb = float((Eb.max() - Eb.min()) / (Eb.max() + Eb.min()))
    s = add(6, "A short bake lets the chemical change spread a little. That smooths ripples, "
               "but too much spreading blurs the edges.",
            moisture=moist, hmds=cover, film=film, latent=Eb,
            metrics={"Blur (diffusion length)": f"{sig:.0f} nm", "Contrast after PEB": f"{Mb*100:.0f} %"})
    s["e0"], s["mask_blocks"] = e0, False
    if sig > 0.15 * p.cd_nm:
        s["warnings"].append("PEB blur is large compared to the feature size: edges will round off.")

    # 8 develop
    if p.tone == "positive":
        f = np.clip(1 - GAMMA * np.log10(np.maximum(Eb, 1e-9) / e0), 0, 1)
    else:
        f = np.clip(GAMMA * np.log10(np.maximum(Eb, 1e-9) / e0), 0, 1)
    tf = min(1.0, p.dev_s / 45.0)
    f = 1 - (1 - f) * tf
    if p.dev_s > 90:
        f = np.clip(f - 0.2 * (p.dev_s - 90) / 90.0, 0, 1)
    if adh < 0.6:
        f = f * min(1.0, 0.4 + adh)
    h = t1 * f
    cd, ang = _measure(h, x, t1)
    s = add(7, "The wafer is dipped in developer, which washes away the part of the resist that "
               "light changed (positive tone). What remains is the pattern.",
            moisture=moist, hmds=cover, film=h, metrics={
                "Printed line width": f"{cd:.0f} nm", "Target CD": f"{p.cd_nm:.0f} nm",
                "Sidewall angle": f"{ang:.0f} deg"})
    if h.min() > 0.5 * t1:
        s["warnings"].append("Nothing cleared: dose too low (or contrast too low), so the film is still one solid sheet.")
    elif h.min() > 0.1 * t1:
        s["warnings"].append("Dose looks too low: resist is left in the bright spaces.")
    if h.max() < 0.5 * t1:
        s["warnings"].append("Almost no resist survives: dose too high, over-developed, or contrast too low.")
    if p.dev_s < 45:
        s["warnings"].append("Under-developed: thin resist scum is left in the spaces.")
    if p.dev_s > 90:
        s["warnings"].append("Over-developed: lines are being eaten away.")
    if abs(cd - p.cd_nm) > 0.1 * p.cd_nm and h.max() >= 0.5 * t1:
        s["warnings"].append("Printed width is more than 10% off the target (adjust dose).")

    # 9 hard bake
    sig_h = max(0.0, p.hard_T - 125.0) * 0.8 * np.sqrt(p.hard_s / 120.0)
    hh = _blur(h, sig_h / dxn)
    cd2, ang2 = _measure(hh, x, t1)
    s = add(8, "A last, hotter bake hardens the resist so it survives the next etch or implant. "
               "Too hot and the lines slump (reflow).",
            moisture=moist, hmds=cover, film=hh, metrics={
                "Final line width": f"{cd2:.0f} nm", "Sidewall angle": f"{ang2:.0f} deg",
                "Overlay error": f"{p.overlay_nm:.0f} nm"})
    if p.hard_T > 140:
        s["warnings"].append("Hard-bake is hot enough to make the resist flow and round the lines.")
    return states
