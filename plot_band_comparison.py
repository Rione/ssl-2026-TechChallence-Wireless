#!/usr/bin/env python3
"""Compare 5 GHz vs 6 GHz: throughput, latency, and JP regulatory channel map.

Outputs:
  band_comparison_throughput.{png,pdf}  - TCP/UDP throughput + latency bars
  band_comparison_spectrum.{png,pdf}    - usable vs DFS channel counts (JP)
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plot_ping_test import load_ping

WORKDIR = Path(__file__).parent

C5 = "#f59e0b"   # amber for 5 GHz
C6 = "#2563eb"   # blue for 6 GHz

# (label, 5 GHz file suffix, 6 GHz file suffix)
TCP = ("iperf_tcp_max_bandwidth_test.json", "iperf_tcp_max_bandwidth_test_6ghz.json")
UDP200 = ("iperf_udp_test.json", "iperf_udp_test_6ghz.json")
UDP20 = ("iperf_udp_20mbps_test.json", "iperf_udp_20mbps_test_6ghz.json")

PING_IDLE = ("ping_test.txt", "ping_test_6ghz.txt")
PING_LOAD_DOWN = ("ping_during_udp_20mbps.txt", "ping_during_udp_20mbps_6ghz.txt")
PING_LOAD_UP = ("ping_during_udp_20mbps_from_rock5a.txt",
                "ping_during_udp_20mbps_from_rock5a_6ghz.txt")

# JP regulatory channel map (from `iw phy phy0 channels`, country JP, on the ROCK 5A)
CHANNELS = {
    "5 GHz": {"non_dfs": 8, "dfs": 16},
    "6 GHz": {"non_dfs": 22, "dfs": 0},
}


def load_json(path: Path):
    text = path.read_text()
    i = text.find("{")
    return json.loads(text[i:])


def tcp_mean(path: Path) -> float:
    return load_json(path)["end"]["sum_received"]["bits_per_second"] / 1e6


def udp_recv(path: Path) -> float:
    return load_json(path)["end"].get("sum_received", {}).get("bits_per_second", 0) / 1e6


def ping_mean(path: Path) -> float:
    if not path.exists():
        return float("nan")
    _, rtt, _, meta = load_ping(path)
    return meta.get("avg_ms", float("nan"))


def plot_throughput(out_base: Path):
    tcp = [tcp_mean(WORKDIR / TCP[0]), tcp_mean(WORKDIR / TCP[1])]
    udp200 = [udp_recv(WORKDIR / UDP200[0]), udp_recv(WORKDIR / UDP200[1])]
    udp20 = [udp_recv(WORKDIR / UDP20[0]), udp_recv(WORKDIR / UDP20[1])]

    idle = [ping_mean(WORKDIR / PING_IDLE[0]), ping_mean(WORKDIR / PING_IDLE[1])]
    load_down = [ping_mean(WORKDIR / PING_LOAD_DOWN[0]), ping_mean(WORKDIR / PING_LOAD_DOWN[1])]
    load_up = [ping_mean(WORKDIR / PING_LOAD_UP[0]), ping_mean(WORKDIR / PING_LOAD_UP[1])]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))
    fig.suptitle(
        "5 GHz vs 6 GHz (Wi-Fi 6E) — Throughput & Latency\n"
        "Intel AX210 on ROCK 5A, same AP, robot -> macOS",
        fontsize=13, fontweight="bold", y=1.02,
    )

    # Throughput grouped bars
    groups = ["TCP\n(greedy)", "UDP\n200 Mbps", "UDP\n20 Mbps"]
    x = np.arange(len(groups))
    w = 0.38
    vals5 = [tcp[0], udp200[0], udp20[0]]
    vals6 = [tcp[1], udp200[1], udp20[1]]
    b1 = ax1.bar(x - w / 2, vals5, w, label="5 GHz", color=C5, edgecolor="white")
    b2 = ax1.bar(x + w / 2, vals6, w, label="6 GHz", color=C6, edgecolor="white")
    ax1.set_xticks(x)
    ax1.set_xticklabels(groups)
    ax1.set_ylabel("Throughput received (Mbps)")
    ax1.set_title("Throughput (receiver)", fontsize=11)
    ax1.legend(loc="upper right", fontsize=9)
    for bars in (b1, b2):
        for bar in bars:
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                     f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8)

    # Latency grouped bars
    lgroups = ["Idle", "20 Mbps load\n(down)", "20 Mbps load\n(up)"]
    lx = np.arange(len(lgroups))
    lvals5 = [idle[0], load_down[0], load_up[0]]
    lvals6 = [idle[1], load_down[1], load_up[1]]
    c1 = ax2.bar(lx - w / 2, lvals5, w, label="5 GHz", color=C5, edgecolor="white")
    c2 = ax2.bar(lx + w / 2, lvals6, w, label="6 GHz", color=C6, edgecolor="white")
    ax2.set_xticks(lx)
    ax2.set_xticklabels(lgroups)
    ax2.set_ylabel("Mean RTT (ms)")
    ax2.set_title("Round-trip latency", fontsize=11)
    ax2.legend(loc="upper left", fontsize=9)
    for bars in (c1, c2):
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                     f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=8)

    fig.text(0.5, -0.02,
             "Peak throughput and latency are comparable between bands on a quiet bench — "
             "the 6 GHz advantage is spectrum availability (see channel-map figure).",
             ha="center", fontsize=8.5, color="#374151")
    fig.tight_layout()

    png = out_base.with_suffix(".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    return png


def plot_spectrum(out_base: Path):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    fig.suptitle(
        "JP Regulatory Channel Map — 5 GHz vs 6 GHz\n"
        "from `iw phy phy0 channels` (country JP) on the AX210",
        fontsize=13, fontweight="bold", y=1.02,
    )

    bands = list(CHANNELS.keys())
    x = np.arange(len(bands))
    non_dfs = [CHANNELS[b]["non_dfs"] for b in bands]
    dfs = [CHANNELS[b]["dfs"] for b in bands]

    b1 = ax.bar(x, non_dfs, 0.5, label="Usable, non-DFS (no CAC, no radar eviction)",
                color="#16a34a", edgecolor="white")
    b2 = ax.bar(x, dfs, 0.5, bottom=non_dfs,
                label="DFS / radar channels (CAC delay + eviction risk)",
                color="#dc2626", alpha=0.85, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(bands)
    ax.set_ylabel("20 MHz channels (JP)")
    ax.legend(loc="upper left", fontsize=9)

    for b in bands:
        i = bands.index(b)
        nd = CHANNELS[b]["non_dfs"]
        df = CHANNELS[b]["dfs"]
        ax.text(i, nd / 2, f"{nd}", ha="center", va="center",
                color="white", fontsize=11, fontweight="bold")
        if df:
            ax.text(i, nd + df / 2, f"{df}", ha="center", va="center",
                    color="white", fontsize=11, fontweight="bold")
        ax.text(i, nd + df + 0.7, f"{nd + df} total", ha="center", fontsize=9, color="#374151")

    fig.text(0.5, -0.02,
             "6 GHz exposes 22 immediately-usable channels and zero DFS channels; "
             "5 GHz leaves only 8 non-DFS channels after removing 16 radar-encumbered ones.",
             ha="center", fontsize=8.5, color="#374151")
    fig.tight_layout()

    png = out_base.with_suffix(".png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    return png


def main():
    p1 = plot_throughput(WORKDIR / "band_comparison_throughput")
    print(f"Wrote {p1}")
    p2 = plot_spectrum(WORKDIR / "band_comparison_spectrum")
    print(f"Wrote {p2}")


if __name__ == "__main__":
    main()
