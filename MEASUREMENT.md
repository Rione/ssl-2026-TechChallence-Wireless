# Measurement Methodology — Team Ri-one (Wi-Fi TC 2026)

This document describes **how each metric in the submission was measured**, including exact commands, topology, raw-tool output, post-processing scripts, and known limitations. Results themselves are summarized in [README.md](README.md) Section 4.

## Table of Contents

- [1. Test Topology and Endpoints](#1-test-topology-and-endpoints)
- [2. Software Versions](#2-software-versions)
- [3. Round-Trip Latency (ICMP Ping)](#3-round-trip-latency-icmp-ping)
  - [3.1 Idle baseline (long soak test)](#31-idle-baseline-long-soak-test)
  - [3.2 Latency under 20 Mbps UDP load](#32-latency-under-20-mbps-udp-load)
- [4. Throughput / Data Rate (iperf3)](#4-throughput--data-rate-iperf3)
  - [4.1 TCP — maximum achievable bandwidth](#41-tcp--maximum-achievable-bandwidth)
  - [4.2 UDP — 200 Mbps target (link ceiling)](#42-udp--200-mbps-target-link-ceiling)
  - [4.3 UDP — 20 Mbps target (NPU debug-stream profile)](#43-udp--20-mbps-target-npu-debug-stream-profile)
  - [4.4 How throughput statistics are computed](#44-how-throughput-statistics-are-computed)
- [5. Start-Up Time (Association + DHCP)](#5-start-up-time-association--dhcp)
  - [5.1 Commands](#51-commands)
  - [5.2 `systemd-analyze` output (captured 2026-06-27)](#52-systemd-analyze-output-captured-2026-06-27)
  - [5.3 Journal timeline (`ifup@wlan0.service`, same boot)](#53-journal-timeline-ifupwlan0service-same-boot)
  - [5.4 Reproducing on a fresh boot](#54-reproducing-on-a-fresh-boot)
- [6. Power Consumption](#6-power-consumption)
  - [6.1 Setup](#61-setup)
  - [6.2 Results (single sample each)](#62-results-single-sample-each)
  - [6.3 Limitations](#63-limitations)
- [7. Interference Detection / Channel Utilization](#7-interference-detection--channel-utilization)
  - [7.1 6 GHz link quality (`iw station dump`)](#71-6-ghz-link-quality-iw-station-dump)
  - [7.2 HackRF spectrum sweep — 5 GHz band (idle vs. loaded)](#72-hackrf-spectrum-sweep--5-ghz-band-idle-vs-loaded)
- [10. 6 GHz Bench Tests (2026-06-27)](#10-6-ghz-bench-tests-2026-06-27)
  - [10.1 Idle latency (60 FPS cadence)](#101-idle-latency-60-fps-cadence)
  - [10.2 Latency under 20 Mbps UDP load](#102-latency-under-20-mbps-udp-load)
  - [10.3 Throughput (iperf3, 100 s each)](#103-throughput-iperf3-100-s-each)
  - [10.4 5 GHz vs 6 GHz summary](#104-5-ghz-vs-6-ghz-summary)
  - [10.6 Regulatory channel map (DFS vs 6 GHz) — basis for the band-selection argument](#106-regulatory-channel-map-dfs-vs-6-ghz--basis-for-the-band-selection-argument)
  - [10.7 Band-comparison plots](#107-band-comparison-plots)
  - [10.8 6 GHz Wi-Fi bring-up (`wpa_supplicant`)](#108-6-ghz-wi-fi-bring-up-wpa_supplicant)
- [11. Network-Switching Time (shared <-> team network)](#11-network-switching-time-shared---team-network)
  - [11.1 Setup](#111-setup)
  - [11.2 Method](#112-method)
  - [11.3 Results](#113-results)
- [12. Output File Index](#12-output-file-index)
- [13. Known Gaps Before Final Submission](#13-known-gaps-before-final-submission)

---

## 1. Test Topology and Endpoints

| Role | Device | IP address | OS / notes |
|---|---|---|---|
| Robot (client / sender) | Radxa ROCK 5A + Intel AX210NGW | `172.15.0.47` (eth0) / `172.15.0.49` (wlan0, 6 GHz DHCP) / `172.15.0.22` (wlan0, 5 GHz DHCP) | Debian 13 (DietPi), kernel `6.1.115-vendor-rk35xx`, `iperf 3.18`, SSH user `root` |
| Base station (server / receiver) | macOS | `172.15.0.44` | `iperf 3.21`, ICMP ping source for baseline tests |
| Default gateway / DHCP | (AP or router) | `172.15.0.1` | Assigns wlan0 address via DHCP (e.g. `172.15.0.22` during 5 GHz runs) |

**SSH / management:** use `ssh root@172.15.0.47` over **eth0**. Throughput tests bind to the robot's **wlan0** address (`-B 172.15.0.49` on 6 GHz, `172.15.0.22` on 5 GHz).

**Traffic direction for throughput tests:** ROCK 5A → macOS (robot transmits, base station receives).

**Wireless link — 5 GHz bench (2026-06-27, superseded for TC claim):**

```
SSID: SSL_Rione
BSSID: be:fc:e7:37:c6:59
Frequency: 5180 MHz (channel 36, 20 MHz width) — 5 GHz
```

**Wireless link — 6 GHz bench (2026-06-27, primary for Wi-Fi 6E claim):**

```
SSID: SSL_Rione_6G
BSSID: be:fc:e7:37:c6:5a
Frequency: 5975 MHz (channel 21, 6 GHz band)
Signal: -51 dBm
TX rate: 286.7 Mbit/s (802.11ax HE-MCS 11, 2 spatial streams)
Security: WPA3-Personal (SAE, H2E)
Robot wlan0 DHCP: 172.15.0.49
```

> **Note:** 6 GHz association requires `sae_pwe=1` in the global section of `wpa_supplicant.conf` (SAE Hash-to-Element). See Section 10.

---

## 2. Software Versions

| Tool | ROCK 5A | macOS |
|---|---|---|
| iperf3 | 3.18 | 3.21 |
| ping | iputils (Linux) | macOS built-in |
| Wi-Fi driver | `iwlwifi` (in-tree) | — |
| Plotting | — | Python 3 + matplotlib (`plot_*.py` in this repo) |

---

## 3. Round-Trip Latency (ICMP Ping)

### 3.1 Idle baseline (long soak test)

**Goal:** Measure RTT distribution with no competing traffic.

**Command (macOS → ROCK 5A):**

```bash
ping 172.15.0.22 -i 0.016 -c 7625 > ping_test.txt
```

| Flag | Meaning |
|---|---|
| `-i 0.016` | Inter-packet interval **0.016 s** (~62.5 probes/s), modelling **60 FPS** telemetry cadence |
| `-c 7625` | Fixed probe count (7625 × 0.016 s ≈ **122 s** wall time at full rate) |

**Raw output file:** `ping_test.txt`

**Summary line (from capture):**

```
7625 packets transmitted, 7623 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 0.931/1.560/19.224/0.716 ms
```

**Post-processing:**

```bash
python3 plot_ping_test.py ping_test.txt ping_test
```

Generates `ping_test.png` / `ping_test.pdf` (time series + histogram).

**Reported metrics:**

| Statistic | Value |
|---|---|
| Mean RTT | 1.56 ms |
| Std. dev. (σ) | 0.72 ms |
| Max RTT | 19.22 ms |
| Packet loss | 0.00% (2 probes unacknowledged at end of capture — likely test stop, not link loss) |

---

### 3.2 Latency under 20 Mbps UDP load

**Goal:** Measure RTT while the robot streams 20 Mbps UDP (NPU debug-stream profile).

**Procedure:**

1. Start iperf3 server on macOS (IPv4 only):

   ```bash
   iperf3 -s -p 5201 -4
   ```

2. Start UDP stream from ROCK 5A (background):

   ```bash
   ssh root@172.15.0.22 "iperf3 -c 172.15.0.44 -p 5201 -u -b 20M -t 100"
   ```

3. While the stream runs, ping **both directions** for ~98 s (1 probe/s):

   ```bash
   # macOS → ROCK 5A
   ping -c 98 -i 1 172.15.0.22 > ping_during_udp_20mbps.txt

   # ROCK 5A → macOS
   ssh root@172.15.0.22 "ping -c 98 -i 1 172.15.0.44" > ping_during_udp_20mbps_from_rock5a.txt
   ```

**Raw output files:**

- `ping_during_udp_20mbps.txt`
- `ping_during_udp_20mbps_from_rock5a.txt`

**Summary (from captures):**

| Direction | Mean RTT | Min / Max | Loss |
|---|---|---|---|
| macOS → ROCK 5A | 1.92 ms | 1.18 / 3.23 ms | 0.0% (98/98) |
| ROCK 5A → macOS | 1.67 ms | 1.09 / 3.31 ms | 0.0% (98/98) |

**Post-processing:**

```bash
python3 plot_ping_test.py ping_during_udp_20mbps.txt ping_during_udp_20mbps \
  "During 20 Mbps UDP (ROCK 5A -> macOS)"

python3 plot_ping_test.py ping_during_udp_20mbps_from_rock5a.txt ping_during_udp_20mbps_from_rock5a \
  "During 20 Mbps UDP | Ping from sender"

python3 plot_latency_comparison.py
```

Generates per-direction plots and `latency_udp_20mbps_comparison.png` / `.pdf`.

**Note:** iperf3 UDP **jitter** (inter-arrival time variance at the receiver) is a different quantity from ICMP RTT. Do not compare them directly.

---

## 4. Throughput / Data Rate (iperf3)

**Common setup:**

| Side | Command |
|---|---|
| macOS (server) | `iperf3 -s -p 5201 -4` |
| ROCK 5A (client) | `iperf3 -c 172.15.0.44 -p 5201 …` |

`-4` forces the server to listen on IPv4. Without it, macOS may bind IPv6-only and the ROCK 5A client gets `Connection refused`.

All runs: **100 s duration**, **1 s reporting interval** (`-i 1`), JSON output (`-J`), UDP runs include `--get-server-output` (embeds server-side loss/jitter text in the JSON).

---

### 4.1 TCP — maximum achievable bandwidth

**Command (ROCK 5A):**

```bash
iperf3 -c 172.15.0.44 -p 5201 -t 100 -i 1 -J
```

No `-b` flag → TCP sends as fast as congestion control allows.

| Parameter | Value |
|---|---|
| Protocol | TCP |
| Block size | 131,072 bytes (iperf default for this path) |
| MSS | 1,448 bytes |
| Congestion control | `cubic` |
| Timestamp (UTC) | 2026-06-27 06:01:54 |

**Raw output:** `iperf_tcp_max_bandwidth_test.json`

**Post-processing:**

```bash
python3 plot_iperf_tcp_bandwidth.py
```

**Reported metrics (base-station-received / `sum_received`):**

| Metric | Value |
|---|---|
| Mean throughput | 207.2 Mbps |
| Per-interval σ (1 s bins) | 20.8 Mbps |
| Peak instantaneous | 249.2 Mbps |
| Total retransmits (100 s) | 27 |
| Mean TCP RTT (sender `tcp_info`, under load) | 23.2 ms |
| RTT range | 8.6 – 60.2 ms |

---

### 4.2 UDP — 200 Mbps target (link ceiling)

**Command (ROCK 5A):**

```bash
iperf3 -c 172.15.0.44 -p 5201 -u -b 200M -t 100 -i 1 -J --get-server-output \
  > iperf_udp_test.json
```

| Parameter | Value |
|---|---|
| Target bitrate | 200 Mbps |
| Datagram size | 1,448 bytes |
| Timestamp (UTC) | 2026-06-27 06:23:44 |

**Reported metrics (receiver / `sum_received`):**

| Metric | Value |
|---|---|
| Mean throughput | 188.0 Mbps |
| Per-interval σ | 3.8 Mbps |
| Packet loss | 0.043% (696 / 1,623,711 datagrams) |
| Jitter | 0.031 ms |

Loss clustered around **t ≈ 8–9 s** (up to 408 datagrams/s, 2.5% in that 1 s bin).

**Post-processing:** `python3 plot_iperf_udp.py iperf_udp_test.json iperf_udp_test`

---

### 4.3 UDP — 20 Mbps target (NPU debug-stream profile)

**Command (ROCK 5A):**

```bash
iperf3 -c 172.15.0.44 -p 5201 -u -b 20M -t 100 -i 1 -J --get-server-output \
  > iperf_udp_20mbps_test.json
```

| Parameter | Value |
|---|---|
| Target bitrate | 20 Mbps |
| Timestamp (UTC) | 2026-06-27 06:26:42 |

**Reported metrics (receiver):**

| Metric | Value |
|---|---|
| Mean throughput | 20.00 Mbps |
| Per-interval σ | 0.007 Mbps |
| Packet loss | 0.00% |
| Jitter | 0.15 ms |

**Post-processing:** `python3 plot_iperf_udp.py iperf_udp_20mbps_test.json iperf_udp_20mbps_test`

---

### 4.4 How throughput statistics are computed

1. **Raw data:** iperf3 JSON `intervals[].sum.bits_per_second` (1 s bins).
2. **Mean:** `end.sum_received.bits_per_second` (entire run, receiver side for UDP; `sum_received` for TCP).
3. **Std. dev. (σ):** standard deviation of per-interval `bits_per_second` values over the 100 s run, converted to Mbps.
4. **Loss (UDP):** parsed from `server_output_text` embedded in JSON (receiver-side `Lost/Total Datagrams` per interval); total from `end.sum_received.lost_packets`.
5. **Plots:** `plot_iperf_tcp_bandwidth.py` (throughput + TCP RTT + retransmits), `plot_iperf_udp.py` (throughput + jitter + per-second loss).

---

## 5. Start-Up Time (Association + DHCP)

**Goal:** Time from interface bring-up to a usable IP address, as required by the TC template.

**Measurement approach:** `systemd-analyze` on the ROCK 5A, cross-checked with `journalctl` timestamps for `wpa_supplicant` and `dhclient`.

### 5.1 Commands

```bash
# Overall boot time
systemd-analyze

# Per-unit time (sorted slowest first)
systemd-analyze blame | grep -iE 'network|wlan|ifup|dhcp'

# Dependency chain to network-online
systemd-analyze critical-chain network-online.target

# Wi-Fi / DHCP event log for current boot
journalctl -b -u 'ifup@wlan0.service' --no-pager
```

### 5.2 `systemd-analyze` output (captured 2026-06-27)

```
Startup finished in 2.367s (kernel) + 9.408s (userspace) = 11.776s
graphical.target reached after 9.407s in userspace.
```

**Network-related `blame` entries:**

| Unit | Time |
|---|---|
| `ifup@wlan0.service` | **7.155 s** |
| `ifup@eth0.service` | 5.120 s |
| `ifupdown-pre.service` | 335 ms |
| `networking.service` | 156 ms |

**`critical-chain network-online.target`:**

```
network-online.target @9.351s
└─network.target @9.351s
  └─ifup@wlan0.service @2.194s +7.155s
    └─network-pre.target @2.187s
      └─dietpi-preboot.service @1.874s +310ms
        └─dietpi-ramlog.service @1.778s +88ms
          └─…
```

Interpretation:

- `ifup@wlan0.service` **starts** ~2.19 s after power-on and **runs for 7.16 s** → finishes ~9.35 s.
- **`network-online.target`** is reached at **9.35 s** (includes DietPi pre-boot services before Wi-Fi starts).

### 5.3 Journal timeline (`ifup@wlan0.service`, same boot)

| Wall-clock time | Event |
|---|---|
| 04:38:18 | `Starting ifup@wlan0.service` |
| 04:38:22 | `wpa_supplicant`: `CTRL-EVENT-CONNECTED` (SSID `SSL_Rione`, **5180 MHz**) |
| 04:38:24 | `dhclient`: `DHCPACK` of `172.15.0.22` from `172.15.0.1` |
| 04:38:25 | `dhclient`: `bound to 172.15.0.22` |
| 04:38:25 | `Finished ifup@wlan0.service` |

**Durations from `ifup` start:**

| Milestone | Δt |
|---|---|
| Wi-Fi associated | **~4 s** |
| DHCP lease bound | **~7 s** |
| `ifup@wlan0.service` complete | **7.16 s** (systemd) |

**Value reported in summary table:** **7.16 s** = `ifup@wlan0.service` duration (association + DHCP). End-to-end until `network-online.target`: **9.35 s**.

### 5.4 Reproducing on a fresh boot

```bash
ssh root@172.15.0.47 'reboot'
# wait for host to return, then:
ssh root@172.15.0.47 'systemd-analyze blame; journalctl -b -u ifup@wlan0.service --no-pager'
```

For a stricter “first ping succeeds” metric (alternative definition):

```bash
# on macOS, after power-cycling the robot:
while ! ping -c 1 -W 1 172.15.0.22; do sleep 0.1; done
```

Log timestamps at power-on and first successful reply. This was **not** used for the current table entry.

---

## 6. Power Consumption

**Goal:** Robot-side current draw at 12 V, idle vs. full link load.

### 6.1 Setup

| Item | Detail |
|---|---|
| Measurement point | **12 V DC input** to the robot (ROCK 5A + AX210 module) |
| Instrument | Bench ammeter (single reading per condition) |
| Idle condition | `wlan0` up, associated, **no** `iperf3` / `ping` traffic |
| Loaded condition | During **TCP max-bandwidth test** (~208 Mbps received at base station) |

### 6.2 Results (single sample each)

| Condition | Current | Power (12 V × I) |
|---|---|---|
| Idle | **0.17 A** | **2.0 W** |
| TCP loaded | **0.26 A** | **3.1 W** |
| Δ (loaded − idle) | **+0.09 A** | **+1.1 W** |

### 6.3 Limitations

- **No variance (σ) yet** — each condition is one manual reading.
- Current includes entire ROCK 5A board, not AX210 module in isolation.
- Loaded reading taken during TCP (not UDP 20 Mbps); TCP draws more due to higher throughput and CPU.

**Planned improvement:** N repeated samples per condition; report mean ± σ.

---

## 7. Interference Detection / Channel Utilization

### 7.1 6 GHz link quality (`iw station dump`)

We log per-station RF metrics on the operating 6 GHz link (`SSL_Rione_6G`, 5975 MHz):

```bash
ssh root@172.15.0.47 'iw dev wlan0 station dump'
```

| Metric | Value |
|---|---|
| Signal (current / avg) | **-48 dBm** / -53 dBm |
| Beacon signal avg | -50 dBm |
| Beacon loss | 0 |
| TX retries / TX failed | 0 / 0 |
| RX bitrate | 286.7 Mbit/s (HE-MCS 11, 2 SS) |
| TX bitrate | 58.5 Mbit/s (HE-MCS 3, 2 SS) |

Strong signal (-48 dBm), zero beacon loss, and zero TX retries/failures on the 6 GHz link are consistent with the clean, uncongested spectrum argued for in README §6.C. Raw capture: `iw_survey_station_6ghz.txt`.

### 7.2 HackRF spectrum sweep — 5 GHz band (idle vs. loaded)

Channel occupancy was measured with a **HackRF One** (`hackrf_sweep`, SDR++/`hackrf_sweep` CSV format). The full 5 GHz band (5150–5910 MHz) was swept in two conditions:

| File | Condition |
|---|---|
| `out_base.csv` | Idle — no traffic on the 5 GHz shared network |
| `out.csv` | 5 GHz shared network (`SSL_Rione`, ch36 / 5180 MHz) under **TCP upload load** (ROCK 5A → base-station server, `iperf3 -P 4`) |

```bash
# CSV columns: date, time, hz_low, hz_high, hz_bin_width, num_samples, dB, dB, ...
hackrf_sweep -f 5150:5910 -w 1000000 -N 50 -r out_base.csv   # idle
# While iperf3 upload runs on ROCK 5A (wlan0 -> server):
hackrf_sweep -f 5150:5910 -w 1000000 -N 50 -r out.csv
python3 plot_spectrum_sweep.py   # -> spectrum_sweep_5ghz.png, spectrum_sweep_5ghz_ch36.png
```

`plot_spectrum_sweep.py` averages the sweep passes per 1 MHz bin (in the linear power domain), overlays the two conditions, and plots the smoothed `load − baseline` delta. Two figures are generated: **full band** (5150–5910 MHz, 9-MHz smoothing) and **ch36 zoom** (5160–5220 MHz, 3-MHz smoothing).

**Results:**

| Metric | Value |
|---|---|
| Operating-channel carrier (5180 MHz) | sharp peak ~8–10 dB above noise floor (AP beacon, both conditions) |
| Upload load effect (ch36 zoom) | up to **~+6 dB** at 5175–5178 MHz vs. idle baseline |
| Activity across band | multiple carriers spread over 5150–5910 MHz |
| Noise floor | ≈ -60 dBm/MHz across the band |

Wi-Fi uses the same 20 MHz channel for uplink and downlink (time-multiplexed); the ch36 delta is **not** a separate UL/DL frequency split — upload DATA frames add RF energy on the shared channel, most visible where the always-on beacon does not dominate.

![5 GHz spectrum — full band](spectrum_sweep_5ghz.png)
*Full band (5150–5910 MHz): band-wide incumbent occupancy. README Figure 18.*

![5 GHz spectrum — ch36 zoom](spectrum_sweep_5ghz_ch36.png)
*ch36 zoom (5160–5220 MHz): upload load on the operating channel. README Figure 19.*

**Next step:** an equivalent sweep on the 6 GHz operating channel (5975 MHz), captured with a 6 GHz-capable front-end (the HackRF One tunes up to 6000 MHz).

---

## 10. 6 GHz Bench Tests (2026-06-27)

Same methodology as Sections 3–4, but on **6 GHz** (`SSL_Rione_6G`, 5975 MHz).

> **Critical:** ROCK 5A has **eth0 and wlan0 on the same `/22` subnet**. With both interfaces up, `ip route get 172.15.0.44 from 172.15.0.49` selects **`dev eth0`** even when iperf binds `-B 172.15.0.49` — traffic leaks to wired (~800 Mbps). **Before each throughput run:** `ip link set eth0 down` on the robot and confirm `ip route get … dev wlan0`. SSH to the robot via **`172.15.0.49`** while eth0 is down.

```bash
# on ROCK 5A (via ssh root@172.15.0.49 after eth0 down)
iperf3 -c 172.15.0.44 -p 5201 -B 172.15.0.49 …
```

### 10.1 Idle latency (60 FPS cadence)

```bash
ping 172.15.0.49 -i 0.016 -c 7625 > ping_test_6ghz.txt
```

| Statistic | Value |
|---|---|
| Probes | 7,625 (0.0% loss) |
| Mean RTT | 1.45 ms |
| Std. dev. (σ) | 0.37 ms |
| Max RTT | 18.27 ms |
| Wall time | ~122 s at 60 FPS (`-i 0.016` s) |

**Post-processing:** `python3 plot_ping_test.py ping_test_6ghz.txt ping_test_6ghz "6 GHz | 60 FPS idle baseline"`

### 10.2 Latency under 20 Mbps UDP load

```bash
# macOS → ROCK 5A (wlan0)
ping -c 98 -i 1 172.15.0.49 > ping_during_udp_20mbps_6ghz.txt

# ROCK 5A → macOS
ssh root@172.15.0.47 "ping -c 98 -i 1 -I wlan0 172.15.0.44" > ping_during_udp_20mbps_from_rock5a_6ghz.txt
```

| Direction | Mean RTT | Min / Max | Loss |
|---|---|---|---|
| macOS → ROCK 5A | 1.62 ms | 1.07 / 2.53 ms | 0.0% (98/98) |
| ROCK 5A → macOS | 1.65 ms | 1.22 / 2.48 ms | 0.0% (98/98) |

**Comparison plot:** `python3 plot_latency_comparison.py --6ghz`

### 10.3 Throughput (iperf3, 100 s each)

| Test | Command suffix | Mean (receiver) | σ | Loss / retransmits | Jitter (UDP) |
|---|---|---|---|---|---|
| TCP greedy | `-t 100 -i 1 -J` | **203.9 Mbps** | 21.9 Mbps | 262 retransmits | — |
| UDP 200 Mbps | `-u -b 200M … --get-server-output` | **188.8 Mbps** | — | 0.020% | 0.032 ms |
| UDP 20 Mbps | `-u -b 20M … --get-server-output` | **20.0 Mbps** | — | 0.00% | 0.071 ms |

TCP mean RTT under load: **16.9 ms** (WiFi path; earlier **823 Mbps** figure was invalid — measured with eth0 up, traffic routed over wired).

**Post-test link rate** (`iw dev wlan0 link`): tx **270.8 Mbit/s** HE-MCS 11, 2 SS, 5975 MHz.

**Raw files:** `iperf_tcp_max_bandwidth_test_6ghz.json`, `iperf_udp_test_6ghz.json`, `iperf_udp_20mbps_test_6ghz.json`

**Plots:**

```bash
python3 plot_iperf_tcp_bandwidth.py iperf_tcp_max_bandwidth_test_6ghz.json iperf_tcp_max_bandwidth_test_6ghz
python3 plot_iperf_udp.py iperf_udp_test_6ghz.json iperf_udp_test_6ghz
python3 plot_iperf_udp.py iperf_udp_20mbps_test_6ghz.json iperf_udp_20mbps_test_6ghz
```

### 10.4 5 GHz vs 6 GHz summary

| Metric | 5 GHz (`SSL_Rione`, 5180 MHz) | 6 GHz (`SSL_Rione_6G`, 5975 MHz) |
|---|---|---|
| Idle ping mean | 1.56 ms | 1.45 ms |
| TCP throughput (recv, WiFi only) | 207 Mbps | **204 Mbps** |
| UDP 200 Mbps achieved | 188 Mbps | **189 Mbps** |
| UDP 20 Mbps loss | 0.00% | 0.00% |
| Loaded ping (macOS→robot) | 1.92 ms | 1.62 ms |

6 GHz and 5 GHz throughput are **similar on this bench** (same AP hardware, different band). The decisive 6 GHz advantage is **channel availability and DFS-freedom**, not raw Mbps — see 10.6.

### 10.6 Regulatory channel map (DFS vs 6 GHz) — basis for the band-selection argument

Captured on the ROCK 5A with `iw phy phy0 channels` (country `JP`):

```bash
ssh root@172.15.0.47 'iw phy phy0 channels | grep -c "5[0-9][0-9][0-9] MHz"'   # 5 GHz channel entries
ssh root@172.15.0.47 'iw phy phy0 channels | grep -ic "radar detection"'        # DFS channels
ssh root@172.15.0.47 'iw phy phy0 channels | awk "/595[0-9]|6[0-9][0-9][0-9] MHz/" | grep -vc disabled'  # usable 6 GHz
```

| Metric (JP) | 5 GHz | 6 GHz |
|---|---|---|
| Channel entries listed | 40 | 50 |
| **Radar-detection (DFS) channels** | **16** (ch 52–64, 100–144) | **0** |
| Non-DFS usable 20 MHz channels | **8** (ch 36–48, 149–165) | **22** |
| CAC (Channel Availability Check) before TX | up to 60 s on DFS | none |
| Radar event → forced channel vacate | yes | no |

**Implication:** On 5 GHz, over half the channels require DFS (CAC delay + radar-eviction risk → multi-second link blackout during a match), leaving only 8 heavily-congested non-DFS channels. On 6 GHz the same AX210 sees **zero DFS channels** and **22 clean, immediately-usable channels**, enabling wide (80/160 MHz) operation without channel-planning constraints. This — not peak Mbps — is the core reason the design targets the 6 GHz band of Wi-Fi 6E.

### 10.7 Band-comparison plots

```bash
python3 plot_band_comparison.py
# -> band_comparison_throughput.{png,pdf}  (TCP/UDP throughput + RTT, 5 GHz vs 6 GHz)
# -> band_comparison_spectrum.{png,pdf}    (JP usable vs DFS channel counts)
```

`plot_band_comparison.py` reads the existing 5 GHz and 6 GHz iperf/ping result files plus the hard-coded JP channel counts from 10.6 (`non_dfs` / `dfs`). Update those counts if the regulatory map changes.

### 10.8 6 GHz Wi-Fi bring-up (`wpa_supplicant`)

6 GHz APs advertising **SAE-H2E only** require a global `sae_pwe=1` in `/etc/wpa_supplicant/wpa_supplicant.conf`:

```ini
country=JP
p2p_disabled=1
sae_pwe=1

network={
    ssid="SSL_Rione_6G"
    key_mgmt=SAE
    psk="…"
    ieee80211w=2
    scan_ssid=1
}
```

Without `sae_pwe=1`, `wpa_supplicant` logs `SAE H2E disabled` / `skip - rate sets do not match` and stays in `SCANNING`.

This config (combined with the Section 11.1 dual-network version) is saved in the repo root as [`wpa_supplicant.conf.example`](wpa_supplicant.conf.example) for release/reproducibility.

---

## 11. Network-Switching Time (shared <-> team network)

**Goal:** Quantify how fast the robot switches between the **TC-provided shared network** and the **team's own network** (official TC rule). Modelled with two real SSIDs: team = `SSL_Rione_6G` (6 GHz, WPA3-SAE), shared = `SSL_Rione` (5 GHz, WPA3-SAE).

### 11.1 Setup

Both networks pre-configured in one `wpa_supplicant.conf` (`id 0` = 6 GHz team, `id 1` = 5 GHz shared), each WPA3-SAE with `ieee80211w=2` (5 GHz AP rejects non-PMF clients with `status_code=31`). **Control/SSH over wired eth0 (`172.15.0.47`)** so the Wi-Fi link can be torn down without losing the session.

```ini
country=JP
p2p_disabled=1
sae_pwe=1
network={ id_str="team_6g"   ssid="SSL_Rione_6G" key_mgmt=SAE psk="…" ieee80211w=2 scan_ssid=1 scan_freq=5975 priority=10 }
network={ id_str="shared_5g" ssid="SSL_Rione"    key_mgmt=SAE psk="…" ieee80211w=2 scan_freq=5180 priority=5 }
```

This exact config is saved in the repo root as [`wpa_supplicant.conf.example`](wpa_supplicant.conf.example).

### 11.2 Method

`/tmp/switch_bench.sh` (on the robot) issues `wpa_cli select_network <id>` and polls `wpa_cli status` every 50 ms, timing from `select_network` to `wpa_state=COMPLETED` (scan + SAE auth + 4-way key handshake). 5 trials each direction.

> **6 GHz regdom caveat:** while associated to 5 GHz the AX210's self-managed regdom drops to WORLD and **disables the 6 GHz channels** (`iw phy phy0 channels` shows `5975 MHz (disabled)`). Switching *to* 6 GHz therefore first runs `iw dev wlan0 scan freq 5975` to hear the 6 GHz beacon and re-enable the channel — this scan is the dominant cost of the 6 GHz direction.

### 11.3 Results

| Switch target | Mean | Min / Max | First data (ping) |
|---|---|---|---|
| → 6 GHz team (`SSL_Rione_6G`) | **481 ms** | 352 / 636 ms | assoc + ~10–20 ms |
| → 5 GHz shared (`SSL_Rione`) | **326 ms** | 236 / 457 ms | assoc + ~10–20 ms |

Both networks share the `172.15.0.0/22` subnet, so the DHCP lease is retained across the switch and the first ICMP reply lands ~10–20 ms after `COMPLETED` (no L3 re-acquisition delay). Raw data: `network_switch_test.csv`. Plot: `python3 plot_network_switch.py`.

---

## 12. Output File Index

| File | Contents |
|---|---|
| `ping_test.txt` | Idle ICMP soak (7,625 probes) |
| `ping_during_udp_20mbps.txt` | ICMP under 20 Mbps UDP, macOS → robot |
| `ping_during_udp_20mbps_from_rock5a.txt` | ICMP under 20 Mbps UDP, robot → macOS |
| `iperf_tcp_max_bandwidth_test.json` | TCP 100 s, greedy |
| `iperf_udp_test.json` | UDP 100 s, 200 Mbps target |
| `iperf_udp_20mbps_test.json` | UDP 100 s, 20 Mbps target |
| `plot_ping_test.py` | Ping → PNG/PDF |
| `plot_iperf_tcp_bandwidth.py` | TCP iperf JSON → PNG/PDF |
| `plot_iperf_udp.py` | UDP iperf JSON → PNG/PDF |
| `plot_latency_comparison.py` | Idle vs. loaded ping comparison chart (`--6ghz` for 6 GHz files) |
| `plot_band_comparison.py` | 5 GHz vs 6 GHz throughput/latency + JP channel-map figures |
| `band_comparison_throughput.png` | 5 GHz vs 6 GHz throughput & latency bars |
| `band_comparison_spectrum.png` | JP usable vs DFS channel counts |
| `ping_test_6ghz.txt` | 6 GHz idle ICMP (7,625 probes, 60 FPS) |
| `ping_during_udp_20mbps_6ghz.txt` | 6 GHz ICMP under 20 Mbps UDP, macOS → robot |
| `ping_during_udp_20mbps_from_rock5a_6ghz.txt` | 6 GHz ICMP under 20 Mbps UDP, robot → macOS |
| `iperf_tcp_max_bandwidth_test_6ghz.json` | 6 GHz TCP 100 s |
| `iperf_udp_test_6ghz.json` | 6 GHz UDP 100 s, 200 Mbps target |
| `iperf_udp_20mbps_test_6ghz.json` | 6 GHz UDP 100 s, 20 Mbps target |
| `network_switch_test.csv` | Network-switch timing (5 trials each direction) |
| `plot_network_switch.py` | Switch-time chart |
| `network_switch_test.png` | 6 GHz ↔ 5 GHz switch-time figure |
| `iw_survey_station_6ghz.txt` | 6 GHz station RF capture (signal / retries / bitrate) |
| `out_base.csv` / `out.csv` | HackRF 5 GHz sweep — idle / under load |
| `spectrum_sweep_5ghz.png` | 5 GHz spectrum idle-vs-load comparison (full band) |
| `spectrum_sweep_5ghz_ch36.png` | 5 GHz spectrum zoom on SSL_Rione ch36 (5160-5220 MHz) |
| `plot_spectrum_sweep.py` | script generating the sweep comparison figure |

---

## 13. Known Gaps Before Final Submission

1. ~~**Band confirmation:** Document `iw dev wlan0 link` showing **6 GHz** operation~~ — **done** (5975 MHz, `SSL_Rione_6G`; see Section 10).
2. **Access point identity:** Model/name of AP bridging robot and base station.
3. **Interference captures:** 6 GHz link RF metrics logged and a 5 GHz HackRF sweep captured (Section 7); an equivalent sweep on the 6 GHz operating channel is still to capture (needs a 6 GHz-capable front-end).
4. **Power σ:** Repeated ammeter samples.
5. ~~**Network-switching demo:**~~ — **bench-measured** (Section 11: 481 ms → 6 GHz team, 326 ms → 5 GHz shared). Still to do: integrate into a live friendly-match demo.
6. ~~**README OS line:**~~ — **done.** README Section 3 now lists Debian 13 (DietPi) as the robot OS and Ubuntu 24.04 as the analysis-container OS (see `Dockerfile`).
7. ~~**Reproducible environment:**~~ — **done.** `Dockerfile`, `docker-compose.yml`, `requirements.txt`, and `wpa_supplicant.conf.example` added to the repo; README Setup Instructions now match what's actually here.
8. ~~**Repository URL:**~~ — **done.** README Section 3 now points at the real repo, `github.com/Yuzz1e/ssl-2026-TechChallence-Wireless`. **Still manual:** commit and push the local changes from this pass before the mailing-list link reflects them.

---

*Last updated: 2026-06-27 — reflects bench tests in this repository.*
