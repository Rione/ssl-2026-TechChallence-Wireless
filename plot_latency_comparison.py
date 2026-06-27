#!/usr/bin/env python3
"""Compare idle vs 20 Mbps UDP loaded ping latency."""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plot_ping_test import load_ping

WORKDIR = Path(__file__).parent
OUTPUT_BASE = WORKDIR / "latency_udp_20mbps_comparison"

SCENARIOS = [
    ("Idle (macOS -> ROCK 5A)", WORKDIR / "ping_test.txt", "#94a3b8"),
    ("20 Mbps UDP load\n(macOS -> ROCK 5A)", WORKDIR / "ping_during_udp_20mbps.txt", "#2563eb"),
    ("20 Mbps UDP load\n(ROCK 5A -> macOS)", WORKDIR / "ping_during_udp_20mbps_from_rock5a.txt", "#059669"),
]


SCENARIOS_6GHZ = [
    ("Idle (macOS -> ROCK 5A)", WORKDIR / "ping_test_6ghz.txt", "#94a3b8"),
    ("20 Mbps UDP load\n(macOS -> ROCK 5A)", WORKDIR / "ping_during_udp_20mbps_6ghz.txt", "#2563eb"),
    ("20 Mbps UDP load\n(ROCK 5A -> macOS)", WORKDIR / "ping_during_udp_20mbps_from_rock5a_6ghz.txt", "#059669"),
]


def collect(scenarios=None):
    rows = []
    for label, path, color in scenarios or SCENARIOS:
        if not path.exists():
            continue
        _, rtt_ms, _, meta = load_ping(path)
        rows.append(
            {
                "label": label,
                "color": color,
                "mean": meta["avg_ms"],
                "std": meta["std_ms"],
                "min": meta["min_ms"],
                "max": meta["max_ms"],
                "loss": meta.get("packet_loss_pct", 0),
            }
        )
    return rows


def plot(rows, out_base: Path):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    fig.suptitle(
        ("6 GHz — " if "6ghz" in str(out_base) else "")
        + "Ping Latency: Idle vs During 20 Mbps UDP Stream\n"
        "UDP: ROCK 5A -> macOS  |  Ping measured concurrently",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )

    labels = [r["label"] for r in rows]
    means = [r["mean"] for r in rows]
    stds = [r["std"] for r in rows]
    colors = [r["color"] for r in rows]
    x = np.arange(len(labels))

    ax = axes[0]
    bars = ax.bar(x, means, yerr=stds, capsize=4, color=colors, edgecolor="white", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Mean RTT (ms)")
    ax.set_ylim(bottom=0)
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.08,
                f"{mean:.2f} ms", ha="center", va="bottom", fontsize=9)

    ax = axes[1]
    mins = [r["min"] for r in rows]
    maxs = [r["max"] for r in rows]
    ax.bar(x, [mx - mn for mn, mx in zip(mins, maxs)], bottom=mins, color=colors,
           alpha=0.35, edgecolor=colors, linewidth=1.2)
    ax.scatter(x, means, color=colors, s=40, zorder=5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)

    idle_mean = rows[0]["mean"] if rows else 0
    loaded_mac = next((r["mean"] for r in rows if "macOS ->" in r["label"] and "Idle" not in r["label"]), 0)
    loaded_rock = next((r["mean"] for r in rows if "ROCK 5A ->" in r["label"]), 0)
    footer = (
        f"Idle mean: {idle_mean:.2f} ms  |  "
        f"Under 20 Mbps UDP: macOS->ROCK 5A {loaded_mac:.2f} ms, ROCK 5A->macOS {loaded_rock:.2f} ms  |  "
        f"iperf UDP jitter (receiver): 0.15 ms  |  "
        f"Note: iperf jitter is inter-arrival time, not ICMP RTT"
    )
    fig.text(0.5, -0.02, footer, ha="center", fontsize=8.5, color="#374151")

    fig.tight_layout()

    png_path = out_base.with_suffix(".png")
    pdf_path = out_base.with_suffix(".pdf")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path


def main():
    use_6ghz = "--6ghz" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--6ghz"]
    out_base = Path(args[0]) if args else (
        WORKDIR / "latency_udp_20mbps_comparison_6ghz" if use_6ghz else OUTPUT_BASE
    )
    scenarios = SCENARIOS_6GHZ if use_6ghz else SCENARIOS
    rows = collect(scenarios)
    if not rows:
        raise SystemExit("No ping data files found")
    png_path, pdf_path = plot(rows, out_base)
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
