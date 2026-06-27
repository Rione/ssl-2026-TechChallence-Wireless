#!/usr/bin/env python3
"""Generate latency plots from macOS ping output."""

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

INPUT = Path(__file__).parent / "ping_test.txt"
OUTPUT_BASE = Path(__file__).parent / "ping_test"

HOST_LABELS = {
    "172.15.0.22": "ROCK 5A",
    "172.15.0.49": "ROCK 5A",
    "172.15.0.47": "ROCK 5A",
    "172.15.0.44": "macOS",
}

REPLY = re.compile(
    r"64 bytes from (?P<host>[\d.]+): icmp_seq=(?P<seq>\d+) ttl=\d+ time=(?P<time>[\d.]+) ms"
)
TIMEOUT = re.compile(r"Request timeout for icmp_seq (?P<seq>\d+)")
STATS = re.compile(
    r"(?P<tx>\d+) packets transmitted, (?P<rx>\d+) packets received, "
    r"(?P<loss>[\d.]+)% packet loss"
)
RTT_STATS = re.compile(
    r"(?:round-trip min/avg/max/stddev|rtt min/avg/max/mdev) = "
    r"(?P<min>[\d.]+)/(?P<avg>[\d.]+)/"
    r"(?P<max>[\d.]+)/(?P<std>[\d.]+) ms"
)
REPLY_LINUX = re.compile(
    r"(?P<bytes>\d+) bytes from (?P<host>[\d.]+): icmp_seq=(?P<seq>\d+) "
    r"ttl=\d+ time=(?P<time>[\d.]+) ms"
)
STATS_LINUX = re.compile(
    r"(?P<tx>\d+) packets transmitted, (?P<rx>\d+) received, "
    r"(?P<loss>[\d.]+)% packet loss"
)


def host_label(ip: str) -> str:
    name = HOST_LABELS.get(ip)
    return f"{name} ({ip})" if name else ip


def load_ping(path: Path):
    target_ip = None
    source_ip = None
    rtt_seq = []
    rtt_ms = []
    timeout_seq = []
    summary = {}

    with path.open() as f:
        for line in f:
            line = line.strip()
            if line.startswith("PING "):
                m = re.search(r"PING ([\d.]+)", line)
                if m:
                    target_ip = m.group(1)
                m = re.search(r" from ([\d.]+)", line)
                if m:
                    source_ip = m.group(1)
                continue

            m = REPLY.search(line)
            if m:
                rtt_seq.append(int(m.group("seq")))
                rtt_ms.append(float(m.group("time")))
                continue
            m = REPLY_LINUX.search(line)
            if m:
                rtt_seq.append(int(m.group("seq")))
                rtt_ms.append(float(m.group("time")))
                continue

            m = TIMEOUT.search(line)
            if m:
                timeout_seq.append(int(m.group("seq")))
                continue

            m = STATS.search(line)
            if m:
                summary.update(
                    {
                        "transmitted": int(m.group("tx")),
                        "received": int(m.group("rx")),
                        "packet_loss_pct": float(m.group("loss")),
                    }
                )
                continue
            m = STATS_LINUX.search(line)
            if m:
                summary.update(
                    {
                        "transmitted": int(m.group("tx")),
                        "received": int(m.group("rx")),
                        "packet_loss_pct": float(m.group("loss")),
                    }
                )
                continue

            m = RTT_STATS.search(line)
            if m:
                summary.update(
                    {
                        "min_ms": float(m.group("min")),
                        "avg_ms": float(m.group("avg")),
                        "max_ms": float(m.group("max")),
                        "std_ms": float(m.group("std")),
                    }
                )

    rtt_seq = np.array(rtt_seq)
    rtt_ms = np.array(rtt_ms)
    timeout_seq = np.array(timeout_seq)

    meta = {
        "target_ip": target_ip or "172.15.0.22",
        "count": len(rtt_ms),
        "timeouts": len(timeout_seq),
        **summary,
    }
    if meta["target_ip"] == "172.15.0.44":
        meta["source"] = host_label(source_ip or "172.15.0.22")
        meta["target"] = host_label("172.15.0.44")
    else:
        meta["source"] = host_label("172.15.0.44")
        meta["target"] = host_label(meta["target_ip"])
    if "avg_ms" not in meta and len(rtt_ms):
        meta["min_ms"] = float(np.min(rtt_ms))
        meta["avg_ms"] = float(np.mean(rtt_ms))
        meta["max_ms"] = float(np.max(rtt_ms))
        meta["std_ms"] = float(np.std(rtt_ms))

    return rtt_seq, rtt_ms, timeout_seq, meta


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    if len(values) < window:
        return values.copy()
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="valid")


def plot(rtt_seq, rtt_ms, timeout_seq, meta, out_base: Path, subtitle: str = ""):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [2, 1]})

    title = "ICMP Ping Latency Test"
    if subtitle:
        title += f"\n{subtitle}"
    title += f"\n{meta['source']} -> {meta['target']}"
    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.98)

    ax = axes[0]
    ax.plot(rtt_seq, rtt_ms, color="#2563eb", linewidth=0.4, alpha=0.35, label="Per packet")
    window = 50
    if len(rtt_ms) >= window:
        smooth = rolling_mean(rtt_ms, window)
        smooth_seq = rtt_seq[window - 1 :]
        ax.plot(
            smooth_seq,
            smooth,
            color="#1d4ed8",
            linewidth=1.5,
            label=f"Rolling mean ({window} pkts)",
        )
    ax.axhline(meta["avg_ms"], color="#dc2626", linestyle="--", linewidth=1.2,
               label=f"Mean: {meta['avg_ms']:.2f} ms")
    if len(timeout_seq):
        ymax = max(meta["max_ms"] * 1.1, float(np.max(rtt_ms)) * 1.05)
        ax.scatter(
            timeout_seq,
            [ymax] * len(timeout_seq),
            color="#dc2626",
            marker="x",
            s=28,
            linewidths=1.2,
            label=f"Timeout ({len(timeout_seq)})",
            zorder=5,
        )
    ax.set_ylabel("RTT (ms)")
    ax.set_xlabel("ICMP sequence number")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=9)

    ax = axes[1]
    ax.hist(rtt_ms, bins=50, color="#059669", edgecolor="white", linewidth=0.4, alpha=0.9)
    ax.axvline(meta["avg_ms"], color="#dc2626", linestyle="--", linewidth=1.2,
               label=f"Mean: {meta['avg_ms']:.2f} ms")
    ax.set_xlabel("RTT (ms)")
    ax.set_ylabel("Packet count")
    ax.legend(loc="upper right", fontsize=9)

    loss = meta.get("packet_loss_pct", 0.0)
    tx = meta.get("transmitted", meta["count"] + meta["timeouts"])
    rx = meta.get("received", meta["count"])
    stats = meta.get("footer") or (
        f"Ping: {meta['source']} -> {meta['target']}  |  "
        f"Packets: {rx}/{tx} received  |  "
        f"Loss: {loss:.1f}%  |  "
        f"RTT: {meta['min_ms']:.2f}-{meta['max_ms']:.2f} ms "
        f"(mean {meta['avg_ms']:.2f} ms, std {meta['std_ms']:.2f} ms)  |  "
        f"Timeouts logged: {meta['timeouts']}"
    )
    fig.text(0.5, 0.01, stats, ha="center", fontsize=9, color="#374151")

    fig.tight_layout(rect=[0, 0.04, 1, 0.95])

    png_path = out_base.with_suffix(".png")
    pdf_path = out_base.with_suffix(".pdf")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT
    out_base = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_BASE
    subtitle = sys.argv[3] if len(sys.argv) > 3 else ""

    series = load_ping(input_path)
    png_path, pdf_path = plot(*series, out_base=out_base, subtitle=subtitle)
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
