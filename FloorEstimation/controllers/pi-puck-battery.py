#!/usr/bin/env python3
"""Script to monitor and display Pi-puck battery charge state."""
from time import sleep
from datetime import datetime
import RPi.GPIO as GPIO
import argparse
import subprocess
import os


MIN_VOLTAGE = 3.3
MAX_VOLTAGE = 4.138
CHARGE_MIN_VOLTAGE = 3.778
CHARGE_MAX_VOLTAGE = 4.198
BAT_LOW_VOLTAGE = 3.6
BAT_VLOW_VOLTAGE = 3.5
BAT_CRIT_VOLTAGE = 3.35
VOLTAGE_RANGE = MAX_VOLTAGE - MIN_VOLTAGE
CHARGE_RANGE = CHARGE_MAX_VOLTAGE - CHARGE_MIN_VOLTAGE
# /sys/bus/i2c/devices/11-0048/iio:device0/in_voltage0_raw
# /sys/bus/i2c/devices/3-0048/iio:device0/in_voltage0_raw
# /sys/bus/i2c/drivers/ads1015/11-0048/in4_input
# /sys/bus/i2c/drivers/ads1015/3-0048/in4_input
EPUCK_BATTERY_PATH = "/sys/bus/i2c/devices/{}-0048/iio:device0/in_voltage0_{}"
EPUCK_LEGACY_BATTERY_PATH = "/sys/bus/i2c/drivers/ads1015/{}-0048/in4_input"
EPUCK_LEGACY_BATTERY_SCALE = 1.0
LED_PATH = "/sys/class/leds/pipuck_bat_low"
CHARGE_DETECT_PIN = 33

battery_path = None
scale_path = None
broadcast_messages = False
led_control = False
shutdown_control = False
csv_output = False
quiet_output = False
sent_low_broadcast = False
sent_vlow_broadcast = False


def convert_adc_to_voltage(adc_value, adc_scale):
    """Convert ADC reading to voltage."""
    # return (float(adc_value) + 79.10) / 503.1
    return (float(adc_value) * adc_scale) / 500.0


def get_battery_state():
    """Get battery status."""
    if scale_path is not None:
        with open(scale_path, "r") as scale_file:
            scale = float(scale_file.read())
    else:
        scale = EPUCK_LEGACY_BATTERY_SCALE

    with open(battery_path, "r") as battery_file:
        voltage = convert_adc_to_voltage(battery_file.read(), scale)

    charging = GPIO.input(CHARGE_DETECT_PIN)

    # Attempt to determine the charge/discharge level using some measured constants
    if charging:
        percentage = (voltage - CHARGE_MIN_VOLTAGE) / CHARGE_RANGE
    else:
        percentage = (voltage - MIN_VOLTAGE) / VOLTAGE_RANGE
    if percentage < 0.0:
        percentage = 0.0
    elif percentage > 1.0:
        percentage = 1.0

    return charging, voltage, percentage


def output_level(charging, voltage, percentage):
    """Print battery level output."""
    if not quiet_output:
        if csv_output:
            print(datetime.now(), charging, voltage, percentage)
        else:
            if charging:
                status = "Charging"
            else:
                status = "Discharging"
            print("{} {:.3f}V ({:.2%})".format(status, voltage, percentage))


def set_bat_low_led(state):
    """Set battery low LED state."""
    if led_control:
        with open(os.path.join(LED_PATH, "trigger"), "w") as led_file:
            led_file.write("none")
        with open(os.path.join(LED_PATH, "brightness"), "w") as led_file:
            if state:
                led_file.write("255")
            else:
                led_file.write("0")


def flash_bat_low_led(speed=500):
    """Flash battery low LED with given period."""
    if led_control:
        with open(os.path.join(LED_PATH, "trigger"), "w") as led_file:
            led_file.write("timer")
        with open(os.path.join(LED_PATH, "delay_on"), "w") as led_file:
            led_file.write(str(speed))
        with open(os.path.join(LED_PATH, "delay_off"), "w") as led_file:
            led_file.write(str(speed))


def broadcast_message(message):
    """Send a broadcast message to all users."""
    if broadcast_messages:
        subprocess.run(["wall", message])


def broadcast_level(message, voltage, percentage):
    """Broadcast a battery level message."""
    broadcast_message("Warning: Pi-puck battery level {} ({:.3f}V / {:.2%})".format(message, voltage, percentage))


def trigger_shutdown():
    """Trigger a system shutdown."""
    if shutdown_control:
        broadcast_message("Warning: Pi-puck battery level critical. Shutting down now...")
        subprocess.run(["shutdown", "now"])


def check_battery():
    """Check battery level and respond appropriately."""
    global sent_low_broadcast, sent_vlow_broadcast
    charging, voltage, percentage = get_battery_state()
    output_level(charging, voltage, percentage)
    if not charging:
        if voltage <= BAT_CRIT_VOLTAGE:
            flash_bat_low_led(100)
            broadcast_level("critical", voltage, percentage)
            trigger_shutdown()
        elif voltage <= BAT_VLOW_VOLTAGE:
            flash_bat_low_led()
            if not sent_vlow_broadcast:
                broadcast_level("very low", voltage, percentage)
                sent_vlow_broadcast = True
        elif voltage <= BAT_LOW_VOLTAGE:
            set_bat_low_led(True)
            if not sent_low_broadcast:
                broadcast_level("low", voltage, percentage)
                sent_low_broadcast = True
        else:
            set_bat_low_led(False)
    else:
        set_bat_low_led(False)
        sent_low_broadcast = False
        sent_vlow_broadcast = False


def main():
    """Entry point."""
    global broadcast_messages, led_control, shutdown_control, csv_output, quiet_output, battery_path, scale_path

    parser = argparse.ArgumentParser(description="Monitor Pi-puck battery level.")
    parser.add_argument("-r", "--repeat", action="store_true", help="repeat monitoring in a loop")
    parser.add_argument("-d", "--delay", type=float, default=5, help="repeat delay in seconds (default 5)")
    parser.add_argument("-b", "--broadcast", action="store_true", help="broadcast battery low messages")
    parser.add_argument("-l", "--led", action="store_true", help="control battery low LED (requires root)")
    parser.add_argument("-s", "--shutdown", action="store_true",
                        help="shutdown Raspberry Pi when battery gets critical (requires root)")
    parser.add_argument("-c", "--csv", action="store_true", help="use CSV output format")
    parser.add_argument("-q", "--quiet", action="store_true", help="do not print output to terminal")
    args = parser.parse_args()

    repeat = args.repeat
    delay = args.delay
    broadcast_messages = args.broadcast
    led_control = args.led
    shutdown_control = args.shutdown
    csv_output = args.csv
    quiet_output = args.quiet

    # Determine actual path to use for ADC driver (try iio, then hwmon, on both possible I2C buses)
    if os.path.exists(EPUCK_BATTERY_PATH.format(11, "raw")):
        battery_path = EPUCK_BATTERY_PATH.format(11, "raw")
        scale_path = EPUCK_BATTERY_PATH.format(11, "scale")
    elif os.path.exists(EPUCK_BATTERY_PATH.format(3, "raw")):
        battery_path = EPUCK_BATTERY_PATH.format(3, "raw")
        scale_path = EPUCK_BATTERY_PATH.format(3, "scale")
    elif os.path.exists(EPUCK_LEGACY_BATTERY_PATH.format(11)):
        battery_path = EPUCK_LEGACY_BATTERY_PATH.format(11)
    elif os.path.exists(EPUCK_LEGACY_BATTERY_PATH.format(3)):
        battery_path = EPUCK_LEGACY_BATTERY_PATH.format(3)
    else:
        raise FileNotFoundError

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(CHARGE_DETECT_PIN, GPIO.IN)

    if csv_output and not quiet_output:
        print("datetime, charging, voltage, percentage")

    check_battery()
    
    repeat = False
    if repeat:
        try:
            while True:
                sleep(delay)
                check_battery()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
