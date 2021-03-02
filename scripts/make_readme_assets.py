"""Regenerate docs/spend_curves.gif and print the README benchmark table.

    python scripts/make_readme_assets.py [--auctions 10000000] [--seed 7]
"""
import argparse
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from pacerlab import TrafficConfig, compare, generate_traffic

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--auctions", type=int, default=10_000_000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--frames", type=int, default=48)
    a = p.parse_args()

    tr = generate_traffic(TrafficConfig(n_auctions=a.auctions), a.seed)
    t0 = time.perf_counter()
    df, res = compare(tr, rule="second_price", budget_ratio=0.35, seed=a.seed)
    dt = time.perf_counter() - t0
    base = df.loc["Flat bid", "spend_rmse"]
    print(f"| Strategy | Spend RMSE | Error vs flat | Max dev | Budget used | Win rate | ROAS |")
    print("|---|---|---|---|---|---|---|")
    for name, r in df.iterrows():
        cut = "baseline" if name == "Flat bid" else f"-{100 * (1 - r.spend_rmse / base):.1f}%"
        print(f"| {name} | {r.spend_rmse:.4f} | {cut} | {r.spend_max_dev:.3f} | "
              f"{r.budget_utilization:.1%} | {r.win_rate:.1%} | {r.roas:.2f} |")
    print(f"\n{len(df)} runs x {a.auctions:,} auctions in {dt:.2f}s")

    fig, axes = plt.subplots(1, len(res), figsize=(10, 2.8), sharey=True)
    n = len(next(iter(res.values())).spend)
    ends = np.linspace(n / a.frames, n, a.frames).astype(int)
    lines = []
    for ax, (label, r) in zip(axes, res.items()):
        x = r.time_axis * 24
        ax.plot(x, r.target_cum / r.budget, "--", color="#9a9a9a", lw=1.2)
        (ln,) = ax.plot([], [], color="#2a6fdb", lw=2)
        lines.append((ln, r))
        ax.set_title(label, fontsize=9)
        ax.set_xlim(0, 24)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("Hour", fontsize=8)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Spend / budget", fontsize=8)
    fig.tight_layout()

    def draw(k):
        e = ends[k]
        for ln, r in lines:
            ln.set_data(r.time_axis[: e + 1] * 24, r.spend_cum[: e + 1] / r.budget)
        return [ln for ln, _ in lines]

    out = ROOT / "docs" / "spend_curves.gif"
    out.parent.mkdir(exist_ok=True)
    anim = FuncAnimation(fig, draw, frames=len(ends), blit=True)
    anim.save(out, writer=PillowWriter(fps=12), dpi=70)
    print(f"saved {out} ({out.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
