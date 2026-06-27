#!/usr/bin/env python3
"""Generate throughput / RTT / retransmit plots from iperf3 JSON output."""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

INPUT = Path(__file__).parent / "iperf_tcp_max_bandwidth_test.json"
OUTPUT_BASE = Path(__file__).parent / "iperf_tcp_max_bandwidth_test"

HOST_LABELS = {
    "172.15.0.22": "ROCK 5A",
    "172.15.0.49": "ROCK 5A",
    "172.15.0.47": "ROCK 5A",
    "172.15.0.44": "macOS",
}


def host_label(ip: str) -> str:
    name = HOST_LABELS.get(ip)
    return f"{name} ({ip})" if name else ip


def load_series(path: Path):
    with path.open() as f:
        data = json.load(f)

    times = []
    throughput_mbps = []
    rtt_ms = []
    retransmits = []

    for interval in data["intervals"]:
        s = interval["sum"]
        times.append(s["end"])
        throughput_mbps.append(s["bits_per_second"] / 1e6)
        retransmits.append(s.get("retransmits", 0))
        stream = interval["streams"][0] if interval["streams"] else {}
        rtt_ms.append(stream.get("rtt", 0) / 1000)

    start = data["start"]
    end = data["end"]
    meta = {
        "protocol": start["test_start"]["protocol"],
        "duration_s": start["test_start"]["duration"],
        "client": host_label(start["connected"][0]["local_host"]),
        "server": host_label(start["connecting_to"]["host"]),
        "iperf_version": start["version"],
        "mean_mbps": end["sum_sent"]["bits_per_second"] / 1e6,
        "total_retransmits": end["sum_sent"]["retransmits"],
        "mean_rtt_ms": end["streams"][0]["sender"]["mean_rtt"] / 1000,
        "min_rtt_ms": end["streams"][0]["sender"]["min_rtt"] / 1000,
        "max_rtt_ms": end["streams"][0]["sender"]["max_rtt"] / 1000,
        "congestion": end.get("sender_tcp_congestion", "unknown"),
    }
    return times, throughput_mbps, rtt_ms, retransmits, meta


def plot(times, throughput_mbps, rtt_ms, retransmits, meta, out_base: Path):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fig.suptitle(
        "TCP Max Bandwidth Test (iperf3)\n"
        f"{meta['client']} -> {meta['server']}  |  "
        f"{meta['duration_s']} s  |  {meta['iperf_version']}",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    ax = axes[0]
    ax.plot(times, throughput_mbps, color="#2563eb", linewidth=1.2, label="Instantaneous")
    ax.axhline(meta["mean_mbps"], color="#dc2626", linestyle="--", linewidth=1.2,
               label=f"Mean: {meta['mean_mbps']:.1f} Mbps")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=9)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))

    ax = axes[1]
    ax.plot(times, rtt_ms, color="#059669", linewidth=1.2)
    ax.axhline(meta["mean_rtt_ms"], color="#dc2626", linestyle="--", linewidth=1.0,
               label=f"Mean: {meta['mean_rtt_ms']:.1f} ms")
    ax.set_ylabel("RTT (ms)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=9)

    ax = axes[2]
    ax.bar(times, retransmits, width=0.8, color="#d97706", alpha=0.85, align="edge")
    ax.set_ylabel("Retransmits\n(per 1 s interval)")
    ax.set_xlabel("Elapsed time (s)")
    ax.set_xlim(0, meta["duration_s"])
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    stats = (
        f"Sender: ROCK 5A  |  Receiver: macOS  |  "
        f"Mean throughput: {meta['mean_mbps']:.1f} Mbps  |  "
        f"Total retransmits: {meta['total_retransmits']}  |  "
        f"RTT: {meta['min_rtt_ms']:.1f}-{meta['max_rtt_ms']:.1f} ms "
        f"(mean {meta['mean_rtt_ms']:.1f} ms)  |  "
        f"Congestion: {meta['congestion']}"
    )
    fig.text(0.5, 0.01, stats, ha="center", fontsize=9, color="#374151")

    fig.tight_layout(rect=[0, 0.03, 1, 0.96])

    png_path = out_base.with_suffix(".png")
    pdf_path = out_base.with_suffix(".pdf")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT
    out_base = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_BASE

    series = load_series(input_path)
    png_path, pdf_path = plot(*series, out_base=out_base)
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
