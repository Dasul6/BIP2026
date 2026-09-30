"""
Multi-sensor read: turbidity (A0), pH (A1), dissolved oxygen (A2)
on a single ADS1115, read from a Raspberry Pi.

Run with:  python test_sensors.py
Stop with: Ctrl+C  -- this saves a graph (PNG) and a log (XLSX) of everything
           read during the session into the same folder as this script.
"""
import time
import statistics
from datetime import datetime

import board
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

import matplotlib
matplotlib.use("Agg")  # no display attached over SSH/terminal; save straight to file
import matplotlib.pyplot as plt

from openpyxl import Workbook

# --- Per-channel divider scale ----------------------------------------------
# If a sensor uses a voltage divider (like turbidity's 10k/20k into A0),
# set its scale to 1.5 to undo the 2/3 division. If a sensor's signal goes
# straight into its channel with no divider, leave it at 1.0.
TURBIDITY_SCALE = 1.5   # 10k/20k divider in use
PH_SCALE = 1.5           # Teyleten pH board powered from 5V with a 10k/20k divider
DO_SCALE = 1.0           # DFRobot SEN0237-A: 3.3-5.5V in, 0-3.0V out, no divider needed

# --- Calibration placeholders ------------------------------------------------
# FILL THESE IN using your sensor's actual calibration procedure.
# Leaving them as-is gives a rough, uncalibrated estimate only.

# pH: two-point calibration. Rinse the probe, dip it in pH 7.0 buffer, wait for
# the reading to settle (a minute or so), and record the voltage this script
# prints. Rinse again, repeat in pH 4.0 buffer, and fill in both pairs below.
PH_CAL = {
    "v1": 2.5, "ph1": 7.0,   # voltage reading in pH 7.0 buffer
    "v2": 2.0, "ph2": 4.0,   # voltage reading in pH 4.0 buffer
}

# Dissolved oxygen (DFRobot SEN0237-A): single-point calibration in air.
# Dry the probe, let it sit in open air for a few minutes until the voltage
# reading stabilizes, and record that as v_sat. Look up the saturation value
# for the water/air temperature at calibration time in DO_SAT_TABLE below
# (index = temperature in whole degrees C) and set mg_l_sat to that value.
DO_CAL = {
    "v_sat": 1.5,      # voltage reading in open air (fill in from calibration)
    "mg_l_sat": 8.0,   # DO_SAT_TABLE value at the calibration temperature
}

# DFRobot's published saturation table (mg/L), index 0 = 0C, index 40 = 40C.
DO_SAT_TABLE = [
    14.46, 14.22, 13.82, 13.44, 13.09, 12.74, 12.42, 12.11, 11.81, 11.53,
    11.26, 11.01, 10.77, 10.53, 10.30, 10.08, 9.86, 9.66, 9.46, 9.27,
    9.08, 8.90, 8.73, 8.57, 8.41, 8.25, 8.11, 7.96, 7.82, 7.69,
    7.56, 7.43, 7.30, 7.18, 7.07, 6.95, 6.84, 6.73, 6.63, 6.53, 6.41,
]

SAMPLES = 10
DELAY = 0.05
# -----------------------------------------------------------------------------


def ph_from_voltage(v):
    # Linear interpolation/extrapolation between the two calibration points.
    v1, ph1 = PH_CAL["v1"], PH_CAL["ph1"]
    v2, ph2 = PH_CAL["v2"], PH_CAL["ph2"]
    if v1 == v2:
        return float("nan")
    slope = (ph2 - ph1) / (v2 - v1)
    return ph1 + slope * (v - v1)


def do_from_voltage(v):
    # Simple proportional estimate against the single calibration point.
    # Replace with your sensor's real calibration formula once you have it.
    if DO_CAL["v_sat"] == 0:
        return float("nan")
    return (v / DO_CAL["v_sat"]) * DO_CAL["mg_l_sat"]


def read_channel(chan, scale):
    volts = []
    for _ in range(SAMPLES):
        volts.append(chan.voltage)
        time.sleep(DELAY)
    v = statistics.mean(volts) * scale
    noise = statistics.pstdev(volts) * scale
    return v, noise


def save_outputs(timestamps, elapsed, turbidity_v, ph_v, ph_vals, do_v, do_vals):
    if not timestamps:
        print("No readings were collected, nothing to save.")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    png_path = f"sensor_log_{stamp}.png"
    xlsx_path = f"sensor_log_{stamp}.xlsx"

    # --- Graph: one plot per parameter, sharing the time axis -----------------
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)

    axes[0].plot(elapsed, turbidity_v, color="tab:brown")
    axes[0].set_ylabel("Turbidity (V)")
    axes[0].set_title("Turbidity")

    axes[1].plot(elapsed, ph_vals, color="tab:green")
    axes[1].set_ylabel("pH")
    axes[1].set_title("pH")

    axes[2].plot(elapsed, do_vals, color="tab:blue")
    axes[2].set_ylabel("DO (mg/L)")
    axes[2].set_title("Dissolved Oxygen")
    axes[2].set_xlabel("Elapsed time (s)")

    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)

    # --- Log: every parameter, raw voltage and converted value, to Excel -----
    wb = Workbook()
    ws = wb.active
    ws.title = "Sensor Log"
    ws.append([
        "Timestamp", "Elapsed (s)",
        "Turbidity (V)",
        "pH Voltage (V)", "pH",
        "DO Voltage (V)", "DO (mg/L)",
    ])
    for i in range(len(timestamps)):
        ws.append([
            timestamps[i], round(elapsed[i], 2),
            round(turbidity_v[i], 4),
            round(ph_v[i], 4), round(ph_vals[i], 2),
            round(do_v[i], 4), round(do_vals[i], 2),
        ])
    wb.save(xlsx_path)

    print(f"Saved graph to {png_path}")
    print(f"Saved log to {xlsx_path}")


def main():
    try:
        i2c = board.I2C()
        ads = ADS1115(i2c)
    except ValueError:
        print("ADS1115 not found at 0x48. Run `i2cdetect -y 1` and check wiring.")
        return

    ads.gain = 1  # +/-4.096 V input range

    turbidity_chan = AnalogIn(ads, ads1x15.Pin.A0)
    ph_chan = AnalogIn(ads, ads1x15.Pin.A1)
    do_chan = AnalogIn(ads, ads1x15.Pin.A2)

    print("Reading turbidity (A0), pH (A1), dissolved oxygen (A2). Ctrl+C to stop")
    print("and save a graph (PNG) and log (XLSX) of this session.\n")
    print("Calibration values are placeholders until you fill in PH_CAL and DO_CAL.\n")

    timestamps, elapsed = [], []
    turbidity_v, ph_v, ph_vals, do_v, do_vals = [], [], [], [], []
    start = time.monotonic()

    try:
        while True:
            t_v, t_noise = read_channel(turbidity_chan, TURBIDITY_SCALE)
            p_v, p_noise = read_channel(ph_chan, PH_SCALE)
            d_v, d_noise = read_channel(do_chan, DO_SCALE)

            ph_val = ph_from_voltage(p_v)
            do_val = do_from_voltage(d_v)

            print(
                f"Turbidity: {t_v:.3f} V (+/-{t_noise:.3f})  |  "
                f"pH: {p_v:.3f} V -> {ph_val:.2f} (+/-{p_noise:.3f} V)  |  "
                f"DO: {d_v:.3f} V -> {do_val:.2f} mg/L (+/-{d_noise:.3f} V)"
            )

            timestamps.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            elapsed.append(time.monotonic() - start)
            turbidity_v.append(t_v)
            ph_v.append(p_v)
            ph_vals.append(ph_val)
            do_v.append(d_v)
            do_vals.append(do_val)
    except KeyboardInterrupt:
        print("\nStopped. Saving graph and log...")
        save_outputs(timestamps, elapsed, turbidity_v, ph_v, ph_vals, do_v, do_vals)


if __name__ == "__main__":
    main()