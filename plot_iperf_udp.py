#!/usr/bin/env python3
"""Generate throughput / jitter / loss plots from iperf3 UDP JSON output."""

import json
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

INPUT = Path(__file__).parent / "iperf_udp_test.json"
OUTPUT_BASE = Path(__file__).parent / "iperf_udp_test"

HOST_LABELS = {
    "172.15.0.22": "ROCK 5A",
    "172.15.0.47": "ROCK 5A",
    "172.15.0.44": "macOS",
}

SERVER_INTERVAL = re.compile(
    r"^\[\s*\d+\]\s+"
    r"(?P<start>\d+\.\d+)-(?P<end>\d+\.\d+)\s+sec\s+"
    r"[\d.]+\s+\w+\s+"
    r"(?P<mbps>[\d.]+)\s+Mbits/sec\s+"
    r"(?P<jitter>[\d.]+)\s+ms\s+"
    r"(?P<lost>\d+)/(?P<total>\d+)\s+\((?P<loss_pct>[\d.]+)%\)\s*$"
)


def host_label(ip: str) -> str:
    name = HOST_LABELS.get(ip)
    return f"{name} ({ip})" if name else ip


def parse_server_intervals(text: str):
    times = []
    jitter_ms = []
    lost_packets = []
    loss_pct = []

    for line in text.splitlines():
        line = line.strip()
        if "receiver" in line or "sender" in line:
            continue
        m = SERVER_INTERVAL.match(line)
        if not m:
            continue
        duration = float(m.group("end")) - float(m.group("start"))
        if duration > 2.0:
            continue
        times.append(float(m.group("end")))
        jitter_ms.append(float(m.group("jitter")))
        lost_packets.append(int(m.group("lost")))
        loss_pct.append(float(m.group("loss_pct")))

    return times, jitter_ms, lost_packets, loss_pct


def load_series(path: Path):
    with path.open() as f:
        data = json.load(f)

    times = []
    throughput_mbps = []

    for interval in data["intervals"]:
        s = interval["sum"]
        times.append(s["end"])
        throughput_mbps.append(s["bits_per_second"] / 1e6)

    server_text = data.get("server_output_text", "")
    rx_times, jitter_ms, lost_packets, loss_pct = parse_server_intervals(server_text)

    start = data["start"]
    end = data["end"]
    test = start["test_start"]
    rx = end.get("sum_received", {})

    meta = {
        "protocol": test["protocol"],
        "duration_s": test["duration"],
        "target_mbps": test.get("target_bitrate", 0) / 1e6,
        "client": host_label(start["connected"][0]["local_host"]),
        "server": host_label(start["connecting_to"]["host"]),
        "iperf_version": start["version"],
        "mean_mbps": end["sum_sent"]["bits_per_second"] / 1e6,
        "rx_mean_mbps": rx.get("bits_per_second", 0) / 1e6,
        "jitter_ms": rx.get("jitter_ms", 0),
        "lost_packets": rx.get("lost_packets", 0),
        "total_packets": rx.get("packets", 0),
        "lost_percent": rx.get("lost_percent", 0),
    }
    return times, throughput_mbps, rx_times, jitter_ms, lost_packets, loss_pct, meta


def plot(times, throughput_mbps, rx_times, jitter_ms, lost_packets, loss_pct, meta, out_base: Path):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    target = meta["target_mbps"]
    title_extra = f"target {target:.0f} Mbps" if target else "max bandwidth"
    fig.suptitle(
        f"UDP Bandwidth Test (iperf3) — {title_extra}\n"
        f"{meta['client']} -> {meta['server']}  |  "
        f"{meta['duration_s']} s  |  {meta['iperf_version']}",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    ax = axes[0]
    ax.plot(times, throughput_mbps, color="#2563eb", linewidth=1.2, label="Sent (client)")
    ax.axhline(meta["mean_mbps"], color="#dc2626", linestyle="--", linewidth=1.2,
               label=f"Mean sent: {meta['mean_mbps']:.1f} Mbps")
    if target:
        ax.axhline(target, color="#7c3aed", linestyle=":", linewidth=1.0,
                   label=f"Target: {target:.0f} Mbps")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=9)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))

    ax = axes[1]
    if rx_times:
        ax.plot(rx_times, jitter_ms, color="#059669", linewidth=1.2)
        ax.axhline(meta["jitter_ms"], color="#dc2626", linestyle="--", linewidth=1.0,
                   label=f"Mean: {meta['jitter_ms']:.2f} ms")
        ax.legend(loc="upper right", fontsize=9)
    ax.set_ylabel("Jitter (ms)")
    ax.set_ylim(bottom=0)

    ax = axes[2]
    if rx_times:
        ax.bar(rx_times, lost_packets, width=0.8, color="#d97706", alpha=0.85, align="edge")
    ax.set_ylabel("Lost datagrams\n(per 1 s interval)")
    ax.set_xlabel("Elapsed time (s)")
    ax.set_xlim(0, meta["duration_s"])
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    stats = (
        f"Sender: ROCK 5A  |  Receiver: macOS  |  "
        f"Sent: {meta['mean_mbps']:.1f} Mbps  |  "
        f"Received: {meta['rx_mean_mbps']:.1f} Mbps  |  "
        f"Loss: {meta['lost_percent']:.2f}% ({meta['lost_packets']}/{meta['total_packets']})  |  "
        f"Jitter: {meta['jitter_ms']:.2f} ms"
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
