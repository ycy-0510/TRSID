import time
import board
import neopixel
import busio
import adafruit_ssd1306
from smbus2 import SMBus
import psutil
import os
import glob
from PIL import Image,ImageDraw,ImageFont

OLED_ADDR = 0x3C

I2C_BUS = 1
PCF8574_ADDR = 0x20
SW1_ADDR = 0x01
SW2_ADDR = 0x02

PIXEL_PIN = board.D18
NUM_PIXELS = 8
ORDER = neopixel.GRB

i2c = busio.I2C(board.SCL, board.SDA)

oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=OLED_ADDR)

bus = SMBus(I2C_BUS)

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    NUM_PIXELS,
    brightness=0.5,  # 0.0 to 1.0
    auto_write=False,  # Update by function show()
    pixel_order=ORDER,
)

t = 5


def get_cpu_info() -> str:
    """Get CPU model information from /proc/cpuinfo."""
    if os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "Model" in line or "hardware" in line.lower():
                    return line.split(":")[1].strip()
    return "Unknown CPU"


def get_cpu_usage() -> dict:
    """Get current CPU usage percentage and core count.

    Uses interval=None (non-blocking): returns usage since the previous call,
    so the polling loop is never stalled. Prime it once at startup.
    """
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_core": psutil.cpu_count(logical=True),
    }


def get_ram_info() -> dict:
    """Get RAM usage information."""
    mem = psutil.virtual_memory()
    return {
        "total_md": mem.total / (1024**2),
        "used_md": mem.used / (1024**2),
        "free_md": mem.free / (1024**2),
        "percent": mem.percent,
    }


def get_disk_info() -> list[dict]:
    """Get disk partitions and their usage information."""
    partitions_info = []
    partitions = psutil.disk_partitions()
    for partition in partitions:
        if "loop" in partition.device or not partition.mountpoint:
            continue
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            partitions_info.append(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "free_gb": usage.free / (1024**3),
                    "percent": usage.percent,
                }
            )
        except PermissionError:
            continue
    return partitions_info


def get_temperature() -> float | None:
    """Read CPU temperature from the system thermal interface."""
    path = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(path):
        with open(path) as f:
            temp_raw = int(f.read().strip())
            return temp_raw / 1000.0
    return None


def get_fan_speed() -> int | None:
    """Read fan speed (RPM) from the kernel hwmon interface."""

    for path in glob.glob("/sys/class/hwmon/hwmon*/fan*_input"):
        try:
            with open(path) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            continue
    return None


def get_switch_state() -> tuple[bool, bool]:
    """Read the state of two switches connected to the PCF8574."""
    data = bus.read_byte(PCF8574_ADDR)
    sw1 = not (data & SW1_ADDR)
    sw2 = not (data & SW2_ADDR)
    return sw1, sw2


class State:
    def __init__(self):
        self.cpu_info: str = ""
        self.cpu_usage: dict = {}
        self.ram_info: dict = {}
        self.disk_info: list = []
        self.temperature: float | None = None
        self.fan_speed: int | None = None
        self.page = 0
        self.start_time = time.time()


state = State()


def display_info():
    oled.fill(0)
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    match state.page:
        case -1:
            pass
        case 0:
            # Add CPU image on the left side (0,0) to (32,32)
            icon = Image.open("../assets/cpu.png").resize((32, 32)).convert("1")
            image.paste(icon, (0, 0))
            # Add CPU info text on the right side
            font = ImageFont.load_default()
            draw.text((34, 0), f"CPU: {state.cpu_info}", font=font, fill=255)
            draw.text((34, 10), f"Usage: {state.cpu_usage.get('cpu_percent', 0)}%", font=font, fill=255)
            draw.text((34, 20), f"Cores: {state.cpu_usage.get('cpu_core', 0)}", font=font, fill=255)
        case 1:
            # Add RAM image on the left side (0,0) to (32,32)
            icon = Image.open("../assets/ram.png").resize((32, 32)).convert("1")
            image.paste(icon, (0, 0))
            # Add RAM info text on the right side
            font = ImageFont.load_default()
            draw.text((34, 0), f"RAM Total: {state.ram_info.get('total_md', 0):.1f}MB", font=font, fill=255)
            draw.text((34, 10), f"Used: {state.ram_info.get('used_md', 0):.1f}MB", font=font, fill=255)
            draw.text((34, 20), f"Free: {state.ram_info.get('free_md', 0):.1f}MB", font=font, fill=255)
            draw.text((34, 30), f"Usage: {state.ram_info.get('percent', 0)}%", font=font, fill=255)
        case 2:
            # Add Disk image on the left side (0,0) to (32,32)
            icon = Image.open("../assets/disk.png").resize((32, 32)).convert("1")
            image.paste(icon, (0, 0))
            # Add Disk info text on the right side
            font = ImageFont.load_default()
            if state.disk_info:
                disk = state.disk_info[0]  # Show info for the first disk only
                draw.text((34, 0), f"Disk: {disk['device']}", font=font, fill=255)
                draw.text((34, 10), f"Mount: {disk['mountpoint']}", font=font, fill=255)
                draw.text((34, 20), f"Used: {disk['used_gb']:.1f}GB", font=font, fill=255)
                draw.text((34, 30), f"Free: {disk['free_gb']:.1f}GB", font=font, fill=255)
                draw.text((34, 40), f"Usage: {disk['percent']}%", font=font, fill=255)
            else:
                draw.text((34, 0), "No disk info", font=font, fill=255)
        case 3:
            # Add Temperature image on the left side (0,0) to (32,32)
            icon = Image.open("../assets/temp.png").resize((32, 32)).convert("1")
            image.paste(icon, (0, 0))
            # Add Temperature info text on the right side
            font = ImageFont.load_default()
            if state.temperature is not None:
                draw.text((34, 0), f"Temp: {state.temperature:.1f}°C", font=font, fill=255)
            else:
                draw.text((34, 0), "No temp info", font=font, fill=255)
        case 4:
            # Add Fan image on the left side (0,0) to (32,32)
            icon = Image.open("../assets/fan.png").resize((32, 32)).convert("1")
            image.paste(icon, (0, 0))
            # Add Fan info text on the right side
            font = ImageFont.load_default()
            if state.fan_speed is not None:
                draw.text((34, 0), f"Fan Speed: {state.fan_speed}", font=font, fill=255)
            else:
                draw.text((34, 0), "No fan info", font=font, fill=255)
    oled.image(image)
    oled.show()
    


def _level_color(pct: float) -> tuple[int, int, int]:
    """Map a 0-100 level onto green (low) -> yellow (mid) -> red (high)."""
    if pct < 50:
        return (0, 255, 0)
    if pct < 80:
        return (255, 255, 0)
    return (255, 0, 0)


_last_leds: list[tuple[int, int, int]] | None = None


def control_ws2812():
    """Show the active page's metric as a color bar across the 8 LEDs."""
    # Sleep mode: all LEDs off.
    if state.page == -1:
        pct = 0.0
    else:
        match state.page:
            case 0:
                pct = state.cpu_usage.get("cpu_percent", 0)
            case 1:
                pct = state.ram_info.get("percent", 0)
            case 2:
                pct = state.disk_info[0]["percent"] if state.disk_info else 0
            case 3:
                # Map 30-85 °C onto 0-100 %.
                pct = ((state.temperature or 0) - 30) / (85 - 30) * 100
            case 4:
                # Map 0-8000 RPM onto 0-100 %.
                pct = (state.fan_speed or 0) / 8000 * 100
            case _:
                pct = 0

    pct = max(0.0, min(100.0, float(pct)))
    lit = round(pct / 100 * NUM_PIXELS)
    color = _level_color(pct)
    leds = [color if i < lit else (0, 0, 0) for i in range(NUM_PIXELS)]

    global _last_leds
    if leds == _last_leds:
        return
    _last_leds = leds
    for i, c in enumerate(leds):
        pixels[i] = c
    pixels.show()


SWITCH_INTERVAL = 0.02
REFRESH_INTERVAL = 0.5
PAGE_COUNT = 5
AUTO_ADVANCE = 5


def handle_switches(prev_sw1: bool, prev_sw2: bool) -> tuple[bool, bool, bool]:
    """Poll switches, acting only on the rising edge (press, not hold).

    Returns the current (sw1, sw2) states plus whether the page changed.
    """
    sw1, sw2 = get_switch_state()
    changed = False
    if sw1 and not prev_sw1:  # SW1: toggle sleep mode
        state.page = -1 if state.page != -1 else 0
        state.start_time = time.time()
        changed = True
    if sw2 and not prev_sw2:  # SW2: next page
        state.page = (state.page + 1) % PAGE_COUNT
        state.start_time = time.time()
        changed = True
    return sw1, sw2, changed


def refresh():
    """Fetch data for the active page and update the OLED + LEDs."""
    # Auto-advance to the next page after AUTO_ADVANCE seconds (unless sleeping).
    if state.page != -1 and time.time() - state.start_time >= AUTO_ADVANCE:
        state.start_time = time.time()
        state.page = (state.page + 1) % PAGE_COUNT

    match state.page:
        case 0:
            state.cpu_info = get_cpu_info()
            state.cpu_usage = get_cpu_usage()
        case 1:
            state.ram_info = get_ram_info()
        case 2:
            state.disk_info = get_disk_info()
        case 3:
            state.temperature = get_temperature()
        case 4:
            state.fan_speed = get_fan_speed()

    display_info()
    control_ws2812()


def run():
    prev_sw1 = prev_sw2 = False
    last_refresh = 0.0
    while True:
        prev_sw1, prev_sw2, changed = handle_switches(prev_sw1, prev_sw2)
        now = time.time()
        # Refresh on schedule, or immediately when a button changed the page.
        if changed or now - last_refresh >= REFRESH_INTERVAL:
            last_refresh = now
            refresh()
        time.sleep(SWITCH_INTERVAL)


def main():
    bus.write_byte(PCF8574_ADDR, 0x00)
    oled.fill(0)
    oled.show()
    pixels.fill((0, 0, 0))
    pixels.show()
    psutil.cpu_percent(interval=None)  # prime non-blocking CPU usage
    try:
        run()
    except KeyboardInterrupt:
        oled.fill(0)
        oled.show()
        pixels.fill((0, 0, 0))
        pixels.show()
        bus.close()
        print("Stopped by user.")


if __name__ == "__main__":
    main()