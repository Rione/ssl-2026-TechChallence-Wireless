#!/usr/bin/env python3
"""Compare two hackrf_sweep captures (SDR++ / hackrf_sweep CSV format).

Baseline : out_base.csv  (idle, no traffic on the 5 GHz shared network)
Loaded   : out.csv       (5 GHz network under iperf load)

hackrf_sweep CSV columns:
    date, time, hz_low, hz_high, hz_bin_width, num_samples, dB, dB, ...

Each row holds one (hz_low, hz_high) segment; the trailing dB values are the
power of consecutive `hz_bin_width` bins starting at hz_low. The same band is
swept multiple times (multiple timestamps); we average the passes per bin.

Outputs:
    spectrum_sweep_5ghz.{png,pdf}  - overlaid PSD + (load - base) delta
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

WORKDIR = Path(__file__).parent

BASELINE = WORKDIR / "out_base.csv"
LOADED = WORKDIR / "out.csv"
OUTPUT_BASE = WORKDIR / "spectrum_sweep_5ghz"

C_BASE = "#6b7280"   # gray  - baseline / idle
C_LOAD = "#dc2626"   # red   - 5 GHz under load

# 5 GHz operating channel of the shared network (SSL_Rione), and JP DFS span.
OP_CHANNEL_MHZ = 5180          # UNII-1 ch36, where SSL_Rione lives
DFS_RANGE_MHZ = (5260, 5720)   # JP DFS / radar-detection channels


def load_sweep(path: Path):
    """Return (freqs_mhz sorted, mean_dbm) averaged over all sweep passes."""
    bins = defaultdict(list)  # freq_hz center -> [dB, dB, ...]
    with path.open() as fh:
        for row in csv.reader(fh):
            if len(row) < 7:
                continue
            hz_low = float(row[2])
            bin_w = float(row[4])
            powers = [float(x) for x in row[6:] if x.strip() != ""]
            for j, p in enumerate(powers):
                center = hz_low + bin_w * (j + 0.5)
                bins[center].append(p)
    freqs = np.array(sorted(bins.keys()))
    # average in linear power domain, then back to dB (correct for PSD averaging)
    mean_db = np.array([
        10.0 * np.log10(np.mean(10.0 ** (np.array(bins[f]) / 10.0)))
        for f in freqs
    ])
    return freqs / 1e6, mean_db  # MHz, dBm


def smooth(y, win=9):
    """Rolling mean in linear power domain (odd window, edge-padded)."""
    lin = 10.0 ** (np.asarray(y) / 10.0)
    k = np.ones(win) / win
    pad = win // 2
    lin_p = np.pad(lin, pad, mode="edge")
    sm = np.convolve(lin_p, k, mode="valid")
    return 10.0 * np.log10(sm)


def main():
    fb, pb = load_sweep(BASELINE)
    fl, pl = load_sweep(LOADED)

    # align loaded onto the baseline frequency grid for a clean delta
    pl_on_b = np.interp(fb, fl, pl)

    pb_s = smooth(pb)
    pl_s = smooth(pl_on_b)
    delta = pl_s - pb_s   # smoothed delta (bursty traffic -> use smoothed trend)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.4]},
    )

    # ---- top: overlaid spectra (raw faint + smoothed bold) ----
    ax1.fill_between(DFS_RANGE_MHZ, -100, 0, color="#fde68a", alpha=0.35,
                     label="JP DFS channels (radar)", zorder=0)
    ax1.plot(fb, pb, color=C_BASE, lw=0.5, alpha=0.25)
    ax1.plot(fb, pl_on_b, color=C_LOAD, lw=0.5, alpha=0.25)
    ax1.plot(fb, pb_s, color=C_BASE, lw=2.0, label="Baseline (idle), 9-MHz avg")
    ax1.plot(fb, pl_s, color=C_LOAD, lw=2.0, label="5 GHz under load, 9-MHz avg")
    ax1.axvline(OP_CHANNEL_MHZ, color="#1d4ed8", ls="--", lw=1.2,
                label=f"SSL_Rione ch36 ({OP_CHANNEL_MHZ} MHz)")

    ax1.set_ylabel("Power (dBm / MHz bin)")
    ax1.set_title("5 GHz spectrum: idle baseline vs. network under load "
                  "(HackRF sweep, 1 MHz bins, 2 passes)")
    ax1.set_ylim(min(pb.min(), pl.min()) - 3, max(pb.max(), pl.max()) + 6)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right", fontsize=8, ncol=2)

    # ---- bottom: smoothed delta ----
    ax2.axhline(0, color="#9ca3af", lw=0.8)
    ax2.fill_between(fb, 0, delta, where=delta >= 0, color=C_LOAD, alpha=0.6,
                     label="load > baseline")
    ax2.fill_between(fb, 0, delta, where=delta < 0, color=C_BASE, alpha=0.5,
                     label="load < baseline")
    ax2.axvline(OP_CHANNEL_MHZ, color="#1d4ed8", ls="--", lw=1.2)
    ax2.set_ylabel("Δ load − base (dB, 9-MHz avg)")
    ax2.set_xlabel("Frequency (MHz)")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right", fontsize=8)

    # summary stats annotation (around operating channel, smoothed)
    band_mask = (fb >= 5170) & (fb <= 5250)
    txt = (f"Mean power 5170-5250 MHz (smoothed):\n"
           f"  baseline {pb_s[band_mask].mean():.1f} dBm\n"
           f"  loaded   {pl_s[band_mask].mean():.1f} dBm\n"
           f"  Δ {pl_s[band_mask].mean() - pb_s[band_mask].mean():+.1f} dB\n"
           f"Peak Δ: {delta.max():+.1f} dB @ {fb[np.argmax(delta)]:.0f} MHz")
    ax1.text(0.012, 0.97, txt, transform=ax1.transAxes, va="top", ha="left",
             fontsize=8, family="monospace",
             bbox=dict(boxstyle="round", fc="white", ec="#9ca3af", alpha=0.9))

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUTPUT_BASE}.{ext}", dpi=150, bbox_inches="tight")
    print(f"wrote {OUTPUT_BASE}.png / .pdf")
    print(f"baseline bins: {len(fb)}  loaded bins: {len(fl)}  "
          f"range {fb.min():.0f}-{fb.max():.0f} MHz")
    print(f"peak delta +{delta.max():.1f} dB @ {fb[np.argmax(delta)]:.0f} MHz")


if __name__ == "__main__":
    main()
