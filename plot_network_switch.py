#!/usr/bin/env python3
"""Plot AP/network switching time between the team (6 GHz) and shared (5 GHz) networks."""

import csv
import statistics as st
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

WORKDIR = Path(__file__).parent
INPUT = WORKDIR / "network_switch_test.csv"
OUTPUT_BASE = WORKDIR / "network_switch_test"

C6 = "#2563eb"
C5 = "#f59e0b"


def load(path: Path):
    by_dir = {"to_6G_team": [], "to_5G_shared": []}
    with path.open() as f:
        for row in csv.DictReader(f):
            v = row.get("switch_ms", "")
            if v and v != "TIMEOUT":
                by_dir.setdefault(row["direction"], []).append(int(v))
    return by_dir


def plot(by_dir, out_base: Path):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))
    fig.suptitle(
        "Network-Switching Time — Team (6 GHz) <-> Shared (5 GHz)\n"
        "Intel AX210 on ROCK 5A, wpa_supplicant `select_network`, control over wired eth0",
        fontsize=12.5, fontweight="bold", y=1.03,
    )

    dirs = ["to_6G_team", "to_5G_shared"]
    labels = ["-> 6 GHz\n(team, SSL_Rione_6G)", "-> 5 GHz\n(shared, SSL_Rione)"]
    colors = [C6, C5]

    # Per-trial scatter + mean bar
    x = np.arange(len(dirs))
    means = [st.mean(by_dir[d]) for d in dirs]
    stds = [st.pstdev(by_dir[d]) if len(by_dir[d]) > 1 else 0 for d in dirs]
    bars = ax1.bar(x, means, 0.5, yerr=stds, capsize=5, color=colors, edgecolor="white", alpha=0.85)
    for i, d in enumerate(dirs):
        ax1.scatter([i] * len(by_dir[d]), by_dir[d], color="#111827", s=22, zorder=5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.set_ylabel("Switch time (ms)")
    ax1.set_title("Association switch time (mean +/- σ, dots = trials)", fontsize=10.5)
    for bar, m in zip(bars, means):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 12,
                 f"{m:.0f} ms", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Phase breakdown bar (illustrative composition)
    ax2.axis("off")
    all_vals = by_dir["to_6G_team"] + by_dir["to_5G_shared"]
    summary = (
        "Summary (n = {n6}+{n5} trials)\n"
        "\n"
        "-> 6 GHz team:  mean {m6:.0f} ms  (min {min6:.0f}, max {max6:.0f})\n"
        "-> 5 GHz shared: mean {m5:.0f} ms  (min {min5:.0f}, max {max5:.0f})\n"
        "\n"
        "First data (ping) follows association by ~10-20 ms\n"
        "(same /22 subnet, DHCP lease retained -> no L3 delay).\n"
        "\n"
        "Note: -> 6 GHz includes a 6 GHz scan to re-acquire the\n"
        "regulatory domain (Wi-Fi 6E self-managed regdom); this is\n"
        "the dominant cost. 5 GHz needs no such step."
    ).format(
        n6=len(by_dir["to_6G_team"]), n5=len(by_dir["to_5G_shared"]),
        m6=st.mean(by_dir["to_6G_team"]), min6=min(by_dir["to_6G_team"]), max6=max(by_dir["to_6G_team"]),
        m5=st.mean(by_dir["to_5G_shared"]), min5=min(by_dir["to_5G_shared"]), max5=max(by_dir["to_5G_shared"]),
    )
    ax2.text(0.0, 0.95, summary, va="top", ha="left", fontsize=10, family="monospace",
             color="#1f2937", transform=ax2.transAxes)

    fig.tight_layout()
    png = out_base.with_suffix(".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    return png


def main():
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_BASE
    by_dir = load(inp)
    png = plot(by_dir, out)
    print(f"Wrote {png}")


if __name__ == "__main__":
    main()
