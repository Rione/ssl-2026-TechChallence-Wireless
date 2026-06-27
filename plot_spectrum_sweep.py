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
    spectrum_sweep_5ghz.{png,pdf}        - full band (5150-5910 MHz)
    spectrum_sweep_5ghz_ch36.{png,pdf}   - zoom on SSL_Rione ch36 (5160-5220 MHz)
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

WORKDIR = Path(__file__).parent

BASELINE = WORKDIR / "out_base.csv"
LOADED = WORKDIR / "out.csv"
OUTPUT_FULL = WORKDIR / "spectrum_sweep_5ghz"
OUTPUT_ZOOM = WORKDIR / "spectrum_sweep_5ghz_ch36"

C_BASE = "#6b7280"   # gray  - baseline / idle
C_LOAD = "#dc2626"   # red   - 5 GHz under load

# 5 GHz operating channel of the shared network (SSL_Rione), and JP DFS span.
OP_CHANNEL_MHZ = 5180          # UNII-1 ch36, where SSL_Rione lives
CH36_BW_MHZ = (5170, 5190)     # 20 MHz channel width
ZOOM_RANGE_MHZ = (5160, 5220)  # ch36 neighbourhood for zoom plot
DFS_RANGE_MHZ = (5260, 5720)   # JP DFS / radar-detection channels


def count_sweep_passes(path: Path) -> int:
    """Return number of full-band sweep passes (samples per 1 MHz bin)."""
    bins = defaultdict(list)
    with path.open() as fh:
        for row in csv.reader(fh):
            if len(row) < 7:
                continue
            hz_low = float(row[2])
            bin_w = float(row[4])
            powers = [float(x) for x in row[6:] if x.strip() != ""]
            for j, _ in enumerate(powers):
                center = hz_low + bin_w * (j + 0.5)
                bins[center].append(1)
    if not bins:
        return 0
    sample_counts = [len(v) for v in bins.values()]
    return min(sample_counts) if sample_counts else 0


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


def plot_comparison(
    fb, pb, pl_on_b, n_passes, output_base: Path,
    *, xlim=None, smooth_win=9, show_dfs=False, title_scope: str,
):
    """Render overlaid PSD + delta panel and save png/pdf."""
    pb_s = smooth(pb, win=smooth_win)
    pl_s = smooth(pl_on_b, win=smooth_win)
    delta = pl_s - pb_s

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.4]},
    )

    if show_dfs:
        ax1.fill_between(DFS_RANGE_MHZ, -100, 0, color="#fde68a", alpha=0.35,
                         label="JP DFS channels (radar)", zorder=0)

    ax1.fill_between(CH36_BW_MHZ, -100, 0, color="#bfdbfe", alpha=0.45,
                     label=f"ch36 20 MHz ({CH36_BW_MHZ[0]}-{CH36_BW_MHZ[1]} MHz)",
                     zorder=0)
    ax1.plot(fb, pb, color=C_BASE, lw=0.5, alpha=0.25)
    ax1.plot(fb, pl_on_b, color=C_LOAD, lw=0.5, alpha=0.25)
    smooth_label = f"{smooth_win}-MHz avg" if smooth_win > 1 else "1-MHz bins"
    ax1.plot(fb, pb_s, color=C_BASE, lw=2.0, label=f"Baseline (idle), {smooth_label}")
    ax1.plot(fb, pl_s, color=C_LOAD, lw=2.0, label=f"5 GHz under load, {smooth_label}")
    ax1.axvline(OP_CHANNEL_MHZ, color="#1d4ed8", ls="--", lw=1.2,
                label=f"SSL_Rione ch36 ({OP_CHANNEL_MHZ} MHz)")

    ax1.set_ylabel("Power (dBm / MHz bin)")
    ax1.set_title(
        f"5 GHz spectrum ({title_scope}): idle baseline vs. network under load "
        f"(HackRF sweep, 1 MHz bins, {n_passes} passes)"
    )
    if xlim is not None:
        ax1.set_xlim(xlim)
        view = (fb >= xlim[0]) & (fb <= xlim[1])
        y_lo = min(pb[view].min(), pl_on_b[view].min()) - 3
        y_hi = max(pb[view].max(), pl_on_b[view].max()) + 4
    else:
        y_lo = min(pb.min(), pl_on_b.min()) - 3
        y_hi = max(pb.max(), pl_on_b.max()) + 6
    ax1.set_ylim(y_lo, y_hi)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right", fontsize=8, ncol=2)

    ax2.axhline(0, color="#9ca3af", lw=0.8)
    ax2.fill_between(fb, 0, delta, where=delta >= 0, color=C_LOAD, alpha=0.6,
                     label="load > baseline")
    ax2.fill_between(fb, 0, delta, where=delta < 0, color=C_BASE, alpha=0.5,
                     label="load < baseline")
    ax2.axvline(OP_CHANNEL_MHZ, color="#1d4ed8", ls="--", lw=1.2)
    ax2.set_ylabel(f"Δ load − base (dB, {smooth_label})")
    ax2.set_xlabel("Frequency (MHz)")
    if xlim is not None:
        ax2.set_xlim(xlim)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right", fontsize=8)

    band_mask = (fb >= ZOOM_RANGE_MHZ[0]) & (fb <= ZOOM_RANGE_MHZ[1])
    if xlim is not None:
        band_mask &= (fb >= xlim[0]) & (fb <= xlim[1])
    ch_idx = np.argmin(np.abs(fb - OP_CHANNEL_MHZ))
    txt = (f"Mean power {fb[band_mask].min():.0f}-{fb[band_mask].max():.0f} MHz (smoothed):\n"
           f"  baseline {pb_s[band_mask].mean():.1f} dBm\n"
           f"  loaded   {pl_s[band_mask].mean():.1f} dBm\n"
           f"  Δ {pl_s[band_mask].mean() - pb_s[band_mask].mean():+.1f} dB\n"
           f"ch36 peak (baseline): {pb_s[ch_idx]:.1f} dBm\n"
           f"Peak Δ: {delta[band_mask].max():+.1f} dB @ "
           f"{fb[band_mask][np.argmax(delta[band_mask])]:.0f} MHz")
    ax1.text(0.012, 0.97, txt, transform=ax1.transAxes, va="top", ha="left",
             fontsize=8, family="monospace",
             bbox=dict(boxstyle="round", fc="white", ec="#9ca3af", alpha=0.9))

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{output_base}.{ext}", dpi=150, bbox_inches="tight")
    plt.close(fig)

    peak_i = np.argmax(delta[band_mask]) if band_mask.any() else np.argmax(delta)
    peak_f = fb[band_mask][peak_i] if band_mask.any() else fb[np.argmax(delta)]
    peak_d = delta[band_mask][peak_i] if band_mask.any() else delta.max()
    print(f"wrote {output_base}.png / .pdf  "
          f"(peak Δ {peak_d:+.1f} dB @ {peak_f:.0f} MHz)")
    return peak_d, peak_f


def main():
    fb, pb = load_sweep(BASELINE)
    fl, pl = load_sweep(LOADED)
    pl_on_b = np.interp(fb, fl, pl)
    n_passes = count_sweep_passes(BASELINE)

    plot_comparison(
        fb, pb, pl_on_b, n_passes, OUTPUT_FULL,
        show_dfs=True, smooth_win=9, title_scope="full band",
    )
    plot_comparison(
        fb, pb, pl_on_b, n_passes, OUTPUT_ZOOM,
        xlim=ZOOM_RANGE_MHZ, smooth_win=3, title_scope="ch36 zoom",
    )

    print(f"baseline bins: {len(fb)}  loaded bins: {len(fl)}  "
          f"range {fb.min():.0f}-{fb.max():.0f} MHz")


if __name__ == "__main__":
    main()
