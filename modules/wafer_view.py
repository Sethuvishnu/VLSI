"""
Wafer Cross-Section Illustration
-----------------------------------
Draws a simplified 2D side-view of the wafer stack (substrate, oxide,
photoresist / mask, implanted region) so students get a visual sense of
"what the wafer looks like" after each process step, in addition to the
quantitative graphs.

This is a schematic illustration, not a physically meshed topography
simulation (for that, see tools like ViennaPS or DEVSIM in the README).
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches


LAYER_COLORS = {
    "substrate": "#c9a876",
    "oxide": "#a6cee3",
    "photoresist": "#fdbf6f",
    "polysilicon": "#b2b2b2",
    "metal": "#8c8c8c",
    "nitride": "#cab2d6",
    "implant": "#fb9a99",
}


def draw_wafer_stack(layers, title="Wafer Cross-Section"):
    """
    layers: list of dicts, drawn bottom-to-top, each:
        {"name": "Oxide", "kind": "oxide", "thickness": 0.5}   # thickness in um (relative)
    Substrate is always drawn as a thick base layer automatically.
    """
    fig, ax = plt.subplots(figsize=(6, 4))

    substrate_h = 1.5
    width = 8.0
    y = 0.0

    # substrate base
    ax.add_patch(patches.Rectangle((0, y), width, substrate_h,
                                    facecolor=LAYER_COLORS["substrate"],
                                    edgecolor="black"))
    ax.text(width / 2, y + substrate_h / 2, "Si Substrate",
            ha="center", va="center", fontsize=9)
    y += substrate_h

    # normalize thicknesses for a readable plot (min visual height 0.15)
    max_t = max((l["thickness"] for l in layers), default=1.0) or 1.0
    for layer in layers:
        h = max(0.15, 1.2 * layer["thickness"] / max_t)
        color = LAYER_COLORS.get(layer["kind"], "#dddddd")
        ax.add_patch(patches.Rectangle((0, y), width, h,
                                        facecolor=color, edgecolor="black"))
        label = f'{layer["name"]} ({layer["thickness"]:.3f} um)'
        ax.text(width / 2, y + h / 2, label, ha="center", va="center", fontsize=8)
        y += h

    ax.set_xlim(0, width)
    ax.set_ylim(0, y + 0.3)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title)
    ax.set_aspect("auto")
    fig.tight_layout()
    return fig
