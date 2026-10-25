"""viz3d.py - Plotly 3D scenes for the wafer flow and the litho lab."""
import numpy as np
import plotly.graph_objects as go

LAYER_COLORS = {"oxide": "#8fc7ee", "poly": "#b5543c", "nitride": "#3f9e8a", "metal": "#c9ccd1"}
LAYER_LABELS = {"oxide": "SiO2 (oxide)", "poly": "Polysilicon", "nitride": "Si3N4 (nitride)", "metal": "Aluminium"}
DOPING_SCALE = [[0, "#7f0000"], [0.25, "#e8553d"], [0.4, "#f5c6b8"], [0.5, "#e8e8e8"],
                [0.6, "#bcd4f5"], [0.75, "#3d7be8"], [1, "#00297f"]]
SI_GREY = "#9aa0a8"


def _solid(c):
    return [[0, c], [1, c]]


def box_mesh(boxes, y0, y1, color, name, opacity=1.0, showlegend=True):
    """boxes = [(x0, x1, z0, z1)] -> one Mesh3d."""
    V, I, J, K = [], [], [], []
    tri = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
           (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    for (xa, xb, za, zb) in boxes:
        o = len(V)
        V += [(xa, y0, za), (xb, y0, za), (xb, y1, za), (xa, y1, za),
              (xa, y0, zb), (xb, y0, zb), (xb, y1, zb), (xa, y1, zb)]
        for a, b, c in tri:
            I.append(o + a); J.append(o + b); K.append(o + c)
    if not V:
        return None
    V = np.array(V)
    return go.Mesh3d(x=V[:, 0], y=V[:, 1], z=V[:, 2], i=I, j=J, k=K, color=color, name=name,
                     opacity=opacity, flatshading=True, showlegend=showlegend,
                     lighting=dict(ambient=0.55, diffuse=0.8, specular=0.15), hoverinfo="name")


def _runs(z0, z1, x_edges):
    """Merge neighbouring columns with identical (z0, z1) into boxes."""
    out, start = [], None
    n = len(z0)
    key = lambda i: (round(float(z0[i]), 4), round(float(z1[i]), 4))
    for i in range(n):
        has = z1[i] - z0[i] > 1e-6
        if has and start is None:
            start = i
        if start is not None and (not has or key(i) != key(start)):
            out.append((x_edges[start], x_edges[i], z0[start], z1[start]))
            start = i if has else None
    if start is not None:
        out.append((x_edges[start], x_edges[n], z0[start], z1[start]))
    return out


def _doping_val(net):
    return np.sign(net) * np.clip(np.log10(np.maximum(np.abs(net), 1.0)) - 13, 0, 8)


def _scene(title, height=600, eye=(1.5, -1.9, 0.95), zr=None):
    return dict(
        title=dict(text=title, x=0.01, font=dict(size=15)),
        height=height, margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", y=-0.02),
        scene=dict(aspectmode="data", camera=dict(eye=dict(x=eye[0], y=eye[1], z=eye[2])),
                   xaxis=dict(title="x (um)"), yaxis=dict(title="y (um)"),
                   zaxis=dict(title="height (um)", range=zr)),
    )


# ------------------------------------------------------------------- wafer
def wafer_figure(w, title="Wafer"):
    NX, NZ, dx, Y = w.NX, w.NZ, w.dx, w.YLEN
    xe = np.arange(NX + 1) * dx
    net = w.net_doping()
    val = _doping_val(net)
    first = np.clip(np.searchsorted(w.z, w.si_top), 0, NZ - 1)
    fig = go.Figure()
    cb = dict(title="Net doping", len=0.6, x=1.0, thickness=14,
              tickvals=[-8, -5, -2, 2, 5, 8],
              ticktext=["p 1e21", "p 1e18", "p 1e15", "n 1e15", "n 1e18", "n 1e21"])
    common = dict(colorscale=DOPING_SCALE, cmin=-8, cmax=8, showscale=False, hoverinfo="skip",
                  lighting=dict(ambient=0.8, diffuse=0.5))

    # front cut face (y = 0): doping map; cells above the surface collapse onto it
    Xf = np.repeat(xe[:-1], 2).reshape(NX, 2).copy()
    Xf[:, 1] = xe[1:]
    Xf = np.tile(Xf.reshape(1, -1), (NZ, 1))
    rows = np.maximum(np.arange(NZ)[:, None], first[None, :])
    Zf = -np.maximum(w.z[:, None], w.si_top[None, :])
    Cf = val[rows, np.arange(NX)[None, :]]
    Zf2 = np.repeat(Zf, 2, axis=1)
    Cf2 = np.repeat(Cf, 2, axis=1)
    fig.add_trace(go.Surface(x=Xf, y=np.zeros_like(Xf), z=Zf2, surfacecolor=Cf2, name="Silicon (cut face)",
                             **{**common, "showscale": True}, colorbar=cb))
    # back face
    fig.add_trace(go.Surface(x=Xf, y=np.full_like(Xf, Y), z=Zf2, surfacecolor=np.zeros_like(Zf2),
                             colorscale=_solid("#c4c8ce"), showscale=False, hoverinfo="skip", cmin=0, cmax=1))
    # left/right faces
    for xc, col in ((0.0, 0), (w.WIDTH, NX - 1)):
        Zs = np.tile(-np.maximum(w.z, w.si_top[col])[:, None], (1, 2))
        Cs = np.tile(val[np.maximum(np.arange(NZ), first[col]), col][:, None], (1, 2))
        fig.add_trace(go.Surface(x=np.full((NZ, 2), xc), y=np.tile([0, Y], (NZ, 1)), z=Zs,
                                 surfacecolor=Cs, **common))
    # top surface (vertical walls come from duplicated x points)
    xs = np.empty(2 * NX)
    xs[0::2], xs[1::2] = xe[:-1], xe[1:]
    zt = np.repeat(-w.si_top, 2)
    ct = np.repeat(val[first, np.arange(NX)], 2)
    fig.add_trace(go.Surface(x=np.tile(xs, (2, 1)), y=np.array([[0] * len(xs), [Y] * len(xs)]),
                             z=np.tile(zt, (2, 1)), surfacecolor=np.tile(ct, (2, 1)), **common))

    # films
    base = -w.si_top.copy()
    seen = set()
    for l in w.layers:
        z0, z1 = base.copy(), base + l["t"]
        m = box_mesh(_runs(z0, z1, xe), 0, Y, LAYER_COLORS[l["kind"]], LAYER_LABELS[l["kind"]],
                     showlegend=l["kind"] not in seen)
        seen.add(l["kind"])
        if m is not None:
            fig.add_trace(m)
        base = z1
    top = max(0.4, float((-w.si_top + w.stack_thickness()).max()) + 0.1)
    fig.update_layout(**_scene(title, zr=[-w.DEPTH, top + 0.3]))
    return fig


def profile_figure(w, x_um):
    ix = int(np.clip(x_um / w.dx, 0, w.NX - 1))
    col = w.net_doping()[:, ix]
    valid = w.z >= w.si_top[ix]
    depth = w.z[valid] - w.si_top[ix]
    c = col[valid]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=depth, y=np.where(c > 0, c, np.nan), name="n-type", line=dict(color="#3d7be8")))
    fig.add_trace(go.Scatter(x=depth, y=np.where(c < 0, -c, np.nan), name="p-type", line=dict(color="#e8553d")))
    xj = w.junction_depth(ix)
    if xj:
        fig.add_vline(x=xj, line_dash="dot", annotation_text=f"junction {xj:.3f} um")
    fig.update_yaxes(type="log", title="|net doping| (cm-3)", range=[14, 21.5])
    fig.update_xaxes(title="Depth below silicon surface (um)")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0),
                      title=dict(text=f"Doping profile at x = {w.x[ix]:.2f} um", font=dict(size=14)),
                      legend=dict(orientation="h", y=1.15))
    return fig


# --------------------------------------------------------------------- litho
def litho_figure(s, step_idx):
    x = s["x_nm"] / 1000.0
    L = x[-1] + (x[1] - x[0])
    Y = s["pitch"] / 1000.0
    fig = go.Figure()
    fig.add_trace(box_mesh([(0, L, -0.35, 0)], 0, Y, "#8d939b", "Silicon wafer"))
    if s["moisture"] is not None and step_idx == 0:
        n = int(s["moisture"] * 14)
        rng = np.random.default_rng(1)
        if n:
            fig.add_trace(go.Scatter3d(x=rng.uniform(0, L, n), y=rng.uniform(0, Y, n), z=np.full(n, 0.02),
                                       mode="markers", name="Water molecules",
                                       marker=dict(size=5, color="#2a8cff")))
    if s["hmds"] > 0:
        fig.add_trace(box_mesh([(0, L, 0, 0.02 * min(1, 0.3 + s["hmds"]))], 0, Y, "#f2c94c", "HMDS primer"))
    film = s["film"]
    top_base = 0.02 if s["hmds"] > 0 else 0.0
    if film is not None:
        h = film / 1000.0 + top_base
        X2 = np.tile(x, (2, 1))
        solid = _solid("#e57fb0")
        fig.add_trace(go.Surface(x=X2, y=np.zeros_like(X2), z=np.vstack([np.full_like(h, top_base), h]),
                                 colorscale=solid, showscale=False, hoverinfo="skip", cmin=0, cmax=1))
        fig.add_trace(go.Surface(x=X2, y=np.full_like(X2, Y), z=np.vstack([np.full_like(h, top_base), h]),
                                 colorscale=solid, showscale=False, hoverinfo="skip", cmin=0, cmax=1))
        lat = s["latent"]
        if lat is not None:
            cs = lat
            fig.add_trace(go.Surface(x=X2, y=np.array([np.zeros_like(x), np.full_like(x, Y)]),
                                     z=np.vstack([h, h]), surfacecolor=np.vstack([cs, cs]),
                                     colorscale="YlOrRd", showscale=True, name="Exposure dose",
                                     colorbar=dict(title="Dose (mJ/cm2)", len=0.5, thickness=12),
                                     hoverinfo="skip"))
        else:
            fig.add_trace(go.Surface(x=X2, y=np.array([np.zeros_like(x), np.full_like(x, Y)]),
                                     z=np.vstack([h, h]), surfacecolor=np.zeros((2, len(x))),
                                     colorscale=solid, showscale=False, hoverinfo="skip", cmin=0, cmax=1))
        hmax = float(h.max())
    else:
        hmax = 0.05
    if step_idx == 5 and s.get("mask_blocks"):
        pitch_um = s["pitch"] / 1000.0
        zm = hmax + 0.7
        blocks, rays_x = [], []
        for k in range(int(round(L / pitch_um))):
            c = (k + 0.5) * pitch_um                              # line (dark) centre
            blocks.append((c - pitch_um / 4, c + pitch_um / 4, zm, zm + 0.06))
            rays_x.append(k * pitch_um + (0.0 if k else 0.12 * pitch_um))
        fig.add_trace(box_mesh(blocks, -0.05, Y + 0.05, "#2d2d2d", "Mask (chrome)"))
        rx, rz, ry = [], [], []
        for k in range(int(round(L / pitch_um)) + 1):
            for off in np.linspace(-0.2, 0.2, 4):
                xx = k * pitch_um + off * pitch_um
                if 0 <= xx <= L:
                    for yy in (0.25 * Y, 0.75 * Y):
                        rx += [xx, xx, None]; ry += [yy, yy, None]; rz += [zm + 0.5, hmax, None]
        fig.add_trace(go.Scatter3d(x=rx, y=ry, z=rz, mode="lines", name="UV light",
                                   line=dict(color="#7a3cff", width=4)))
    fig.update_layout(**_scene(s["step"], height=520, eye=(1.3, -1.8, 0.9),
                               zr=[-0.4, max(hmax + 1.0, 1.4)]))
    return fig
