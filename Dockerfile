# Open-source measurement + analysis environment for the Wi-Fi Technical
# Challenge submission (Team Ri-one). Targets Ubuntu 24.04 per the TC's
# reproducibility guidance (see official rules, "Technical Challenge Details").
#
# This container provides:
#   - iperf3, tcpdump, iw   -> the radio measurement tools named in README
#                              Section 3. tcpdump/iw only see real wireless
#                              interfaces if the container is run with
#                              `network_mode: host` + `privileged: true`
#                              (see docker-compose.yml comments). They are not
#                              needed just to regenerate the charts below.
#   - python3 + matplotlib  -> regenerates every chart in README Section 6
#     + numpy                  from the raw ping/iperf3 captures already
#                              committed to this repository (plot_*.py).
#
# Note: this is the *analysis-environment* OS, not the embedded robot OS.
# The actual ROCK 5A bench unit runs Debian 13 (DietPi) — see MEASUREMENT.md
# Section 1.

FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    iperf3 \
    tcpdump \
    iw \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

CMD ["/bin/bash"]
