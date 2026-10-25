"""
wafer3d.py - 2D cross-section wafer model (viz3d.py extrudes it into 3D).

Self-contained: does NOT depend on your other modules, so nothing can
clash with them. Coordinates: x = lateral (um), z = depth below the
ORIGINAL wafer surface (um, positive down).

The wafer keeps:
  * si_top[x]   - where the silicon surface is now (oxidation eats it, etching lowers it)
  * layers      - films stacked above the silicon (oxide / poly / nitride / metal)
  * species     - 2D dopant maps for every implanted dopant
Every step mutates this one object, so later steps see earlier ones.
"""
import copy
import numpy as np

K_B = 8.617e-5      # eV/K
Q = 1.602e-19

# ---- physics tables (simplified, for teaching) -----------------------------
DOPANTS = {   # rp50 = projected range at 50 keV (um), ratio = straggle/range
    "Boron":      dict(kind="p", rp50=0.160, ratio=0.29, exp=0.85, D0=0.76, Ea=3.46),
    "Phosphorus": dict(kind="n", rp50=0.070, ratio=0.43, exp=0.90, D0=3.85, Ea=3.66),
    "Arsenic":    dict(kind="n", rp50=0.034, ratio=0.37, exp=0.80, D0=22.9, Ea=4.10),
}
DEPOSITION = {  # kind, rate (nm/min) at T_ref (C), activation energy (eV)
    "Polysilicon (LPCVD)":     ("poly",    10.0, 620, 1.7),
    "Silicon nitride (LPCVD)": ("nitride",  3.0, 780, 1.8),
    "SiO2 (CVD)":              ("oxide",   25.0, 700, 0.6),
    "Aluminium (sputter)":     ("metal",  100.0,  25, 0.0),
}
ETCH_PROCS = {  # vertical rate nm/min, anisotropy (1 = perfectly vertical walls)
    "RIE (anisotropic)":       (150.0, 0.95),
    "Wet etch (isotropic)":    (100.0, 0.00),
    "DRIE (very anisotropic)": (500.0, 0.99),
}
ETCH_TARGETS = {
    "Non-selective": None,
    "Oxide (SiO2)": {"oxide"},
    "Polysilicon": {"poly"},
    "Nitride": {"nitride"},
    "Metal (Al)": {"metal"},
    "Silicon only": "si",
}


def deal_grove_AB(T_c, ambient):
    kT = K_B * (T_c + 273.15)
    if ambient == "wet":
        B = 386.0 * np.exp(-0.78 / kT)
        BA = 1.63e8 * np.exp(-2.05 / kT)
    else:
        B = 772.0 * np.exp(-1.23 / kT)
        BA = 6.23e6 * np.exp(-2.00 / kT)
    return B / BA, B          # A (um), B (um^2/hr)


def _blur_axis(a, sigma_px, axis):
    if sigma_px < 0.3:
        return a
    sigma_px = min(sigma_px, 80.0)
    r = int(np.ceil(4 * sigma_px))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_px) ** 2)
    k /= k.sum()
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    ap = np.pad(a, pad, mode="reflect")
    out = np.zeros_like(a)
    n = a.shape[axis]
    for j, kj in enumerate(k):
        sl = [slice(None)] * 2
        sl[axis] = slice(j, j + n)
        out += kj * ap[tuple(sl)]
    return out


class Wafer3D:
    NX, NZ = 100, 75
    WIDTH, DEPTH, YLEN = 4.0, 1.5, 1.5      # um

    def __init__(self):
        self.dx = self.WIDTH / self.NX
        self.dz = self.DEPTH / self.NZ
        self.x = (np.arange(self.NX) + 0.5) * self.dx
        self.z = (np.arange(self.NZ) + 0.5) * self.dz
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self):
        self.diameter, self.orientation = 200, "<100>"
        self.substrate = "p-type (Boron)"
        self.bg_signed = -1.4e15            # <0 = p-type, >0 = n-type
        self.si_top = np.zeros(self.NX)
        self.layers = []
        self.species = {}                   # dopant name -> 2D array
        self.log = []

    def snapshot(self):
        return copy.deepcopy(self)

    def si_mask(self):
        return self.z[:, None] >= self.si_top[None, :]

    def net_doping(self):
        net = np.full((self.NZ, self.NX), self.bg_signed)
        for name, arr in self.species.items():
            net += arr if DOPANTS[name]["kind"] == "n" else -arr
        return np.where(self.si_mask(), net, 0.0)

    def stack_thickness(self, kinds=None):
        t = np.zeros(self.NX)
        for l in self.layers:
            if kinds is None or l["kind"] in kinds:
                t += l["t"]
        return t

    def mask_array(self, mask):
        """mask = dict(mode='none'|'inside'|'outside', x0, x1) -> bool[NX] of OPEN columns."""
        if not mask or mask.get("mode", "none") == "none":
            return np.ones(self.NX, bool)
        inside = (self.x >= mask["x0"]) & (self.x <= mask["x1"])
        return inside if mask["mode"] == "inside" else ~inside

    def _mask_species(self):
        m = self.si_mask()
        for k in self.species:
            self.species[k] = np.where(m, self.species[k], 0.0)

    def _clean_layers(self):
        self.layers = [l for l in self.layers if l["t"].max() > 1e-6]

    def junction_depth(self, ix):
        """Depth (um below silicon surface) of first p-n junction in column ix, or None."""
        net = self.net_doping()[:, ix]
        valid = self.z >= self.si_top[ix]
        if not valid.any():
            return None
        col = net[valid]
        s0 = np.sign(col[0]) or 1.0
        flip = np.where(np.sign(col) == -s0)[0]
        if len(flip) == 0:
            return None
        zs = self.z[valid]
        return float(zs[flip[0]] - self.si_top[ix])

    # ------------------------------------------------------------------ steps
    def prep(self, diameter, orientation, substrate, rho):
        self.reset()
        self.diameter, self.orientation, self.substrate = diameter, orientation, substrate
        mu = 450.0 if substrate.startswith("p") else 1350.0
        N = 1.0 / (Q * mu * rho)
        self.bg_signed = -N if substrate.startswith("p") else N
        self.log.append(f"Wafer prep: {diameter} mm {orientation} {substrate}, {rho:g} ohm-cm "
                        f"(doping {N:.1e} cm-3)")

    def oxidize(self, T_c, hours, ambient):
        A, B = deal_grove_AB(T_c, ambient)
        non_oxide = self.stack_thickness({"poly", "nitride", "metal"})
        free = non_oxide < 1e-9
        x0 = self.stack_thickness({"oxide"})
        tau = (x0 ** 2 + A * x0) / B
        x1 = (A / 2.0) * (np.sqrt(1 + (hours + tau) / (A ** 2 / (4 * B))) - 1)
        delta = np.where(free, np.maximum(x1 - x0, 0), 0.0)
        if not self.layers or self.layers[0]["name"] != "Thermal SiO2":
            self.layers.insert(0, dict(name="Thermal SiO2", kind="oxide", t=np.zeros(self.NX)))
        self.layers[0]["t"] = self.layers[0]["t"] + delta
        self.si_top = self.si_top + 0.44 * delta          # oxide eats 44% of its thickness in Si
        self._mask_species()
        self.log.append(f"{ambient.capitalize()} oxidation {T_c} C, {hours:g} h "
                        f"-> up to {delta.max()*1000:.0f} nm grown")

    def implant(self, dopant, energy_kev, dose, mask=None):
        p = DOPANTS[dopant]
        rp = p["rp50"] * (energy_kev / 50.0) ** p["exp"]
        drp = p["ratio"] * rp
        zs = self.z[:, None] - self.si_top[None, :] + self.stack_thickness()[None, :]
        prof = dose / (np.sqrt(2 * np.pi) * drp * 1e-4) * np.exp(-0.5 * ((zs - rp) / drp) ** 2)
        prof = np.where(self.si_mask() & self.mask_array(mask)[None, :], prof, 0.0)
        self.species[dopant] = self.species.get(dopant, np.zeros((self.NZ, self.NX))) + prof
        self.log.append(f"Implant {dopant} {energy_kev} keV, {dose:.0e} cm-2 "
                        f"(Rp {rp*1000:.0f} nm){' [masked]' if mask and mask.get('mode','none')!='none' else ''}")

    def diffuse(self, T_c, minutes):
        t = minutes * 60.0
        m = self.si_mask().astype(float)
        for name, arr in list(self.species.items()):
            p = DOPANTS[name]
            D = p["D0"] * np.exp(-p["Ea"] / (K_B * (T_c + 273.15))) * 1e8   # um^2/s
            s = np.sqrt(2 * D * t)
            num = _blur_axis(_blur_axis(arr * m, s / self.dz, 0), s / self.dx, 1)
            den = _blur_axis(_blur_axis(m, s / self.dz, 0), s / self.dx, 1)
            self.species[name] = np.where(m > 0, num / np.maximum(den, 1e-9), 0.0)
        self.log.append(f"Anneal/diffusion {T_c} C, {minutes:g} min")

    def deposit(self, material, T_c, minutes):
        kind, r0, tref, Ea = DEPOSITION[material]
        rate = r0 * np.exp(-Ea / K_B * (1 / (T_c + 273.15) - 1 / (tref + 273.15)))
        th = rate * minutes / 1000.0
        self.layers.append(dict(name=material.split(" (")[0], kind=kind, t=np.full(self.NX, th)))
        self.log.append(f"Deposit {material.split(' (')[0]} {T_c} C, {minutes:g} min -> {th*1000:.0f} nm")

    def etch(self, proc, depth_nm, target="Non-selective", mask=None, stop_at_si=True):
        _, aniso = ETCH_PROCS[proc]
        d = depth_nm / 1000.0
        L = d * (1 - aniso)                                   # lateral undercut (um)
        openm = self.mask_array(mask)
        if not openm.any():
            self.log.append("Etch skipped (mask closes everything)")
            return
        idx = np.where(openm)[0]
        dist = np.abs(np.arange(self.NX)[:, None] - idx[None, :]).min(axis=1) * self.dx
        if L > 1e-9:
            eff = np.where(dist == 0, d, d * np.sqrt(np.clip(1 - (dist / L) ** 2, 0, 1)))
        else:
            eff = np.where(dist == 0, d, 0.0)
        tg = ETCH_TARGETS[target]
        rem = eff.copy()
        if tg != "si":
            for layer in reversed(self.layers):
                if tg is not None and layer["kind"] not in tg:
                    rem = np.where(layer["t"] > 1e-9, 0.0, rem)    # blocks the etch
                    continue
                take = np.minimum(layer["t"], rem)
                layer["t"] = layer["t"] - take
                rem = rem - take
        stack_gone = self.stack_thickness() < 1e-9
        if tg == "si":
            self.si_top = self.si_top + np.where(stack_gone, eff, 0.0)
        elif tg is None and not stop_at_si:
            self.si_top = self.si_top + np.where(stack_gone, rem, 0.0)
        self._clean_layers()
        self._mask_species()
        self.log.append(f"Etch {proc.split(' (')[0]} {depth_nm:g} nm, target: {target}"
                        f"{' [masked]' if mask and mask.get('mode','none')!='none' else ''}")
