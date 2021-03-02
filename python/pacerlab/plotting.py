"""Spend-vs-time figures (used by the CLI and the Streamlit dashboard)."""

import numpy as np


def spend_curve_figure(results: dict, hours: bool = True):
    """One panel per strategy, side by side, with cumulative spend vs the target."""
    import matplotlib.pyplot as plt

    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n, 3.4), sharey=True, squeeze=False)
    scale = 24.0 if hours else 1.0
    for ax, (label, r) in zip(axes[0], results.items()):
        x = r.time_axis * scale
        ax.plot(x, r.target_cum / r.budget, color="#9a9a9a", ls="--", lw=1.5, label="Target")
        ax.plot(x, r.spend_cum / r.budget, color="#2a6fdb", lw=2, label="Actual")
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Hour of day" if hours else "Day fraction")
        ax.set_xlim(0, scale)
        ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.25)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0][0].set_ylabel("Cumulative spend / budget")
    axes[0][0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    return fig
