"""
Turbidity sensor test: ADS1115 (channel A0) on a Raspberry Pi.

Run with:  python test_turbidity.py
Stop with: Ctrl+C
"""
import time
import statistics

import board
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# --- Settings ---------------------------------------------------------------
# If you use a voltage divider (10k signal->A0, 20k A0->GND), the ADS1115 sees
# only 2/3 of the sensor voltage, so multiply by 1.5 to recover the real value.
# If there is no divider, leave this at 1.0.
DIVIDER_SCALE = 1.5

SAMPLES = 10          # readings averaged per line
DELAY = 0.05          # seconds between samples
# -----------------------------------------------------------------------------


def rough_ntu(v):
    """Approximate NTU from DFRobot's published curve (5V-powered sensor).
    Only meaningful for roughly 2.5 V - 4.2 V. Treat as a ballpark."""
    ntu = -1120.4 * v**2 + 5742.3 * v - 4352.9
    return max(ntu, 0.0)


def describe(v):
    if v < 0.05:
        return "~0 V: check wiring/power (sensor signal may not be reaching A0)"
    if v > 4.5:
        return "very high: check for a wiring issue"
    if v >= 4.0:
        return "clear water / air"
    if v >= 3.0:
        return "slightly cloudy"
    if v >= 2.5:
        return "cloudy"
    return "very cloudy / dirty"


def main():
    try:
        i2c = board.I2C()
        ads = ADS1115(i2c)
    except ValueError:
        print("ADS1115 not found at 0x48. Run `i2cdetect -y 1` and check wiring.")
        return

    ads.gain = 1  # +/-4.096 V input range
    chan = AnalogIn(ads, ads1x15.Pin.A0)

    print("Reading turbidity sensor on A0. Ctrl+C to stop.\n")
    print("Try: sensor in air, in clear water, then in cloudy water "
          "(a drop of milk works). The voltage should DROP as it gets cloudier.\n")

    try:
        while True:
            volts, raws = [], []
            for _ in range(SAMPLES):
                raws.append(chan.value)
                volts.append(chan.voltage)
                time.sleep(DELAY)

            v_adc = statistics.mean(volts)
            v_sensor = v_adc * DIVIDER_SCALE
            noise = statistics.pstdev(volts) * DIVIDER_SCALE

            print(
                f"Raw: {int(statistics.mean(raws)):6d} | "
                f"ADC: {v_adc:.3f} V | "
                f"Sensor: {v_sensor:.3f} V (+/-{noise:.3f}) | "
                f"~{rough_ntu(v_sensor):6.0f} NTU | "
                f"{describe(v_sensor)}"
            )
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
