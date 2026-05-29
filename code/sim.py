"""Desktop simulator for TRSID — run main.py on a Mac/PC without hardware.

It replaces the Raspberry-Pi-only modules (board, busio, neopixel,
adafruit_ssd1306, smbus2) with fakes *before* importing main.py, so main.py
runs completely unmodified. The 128x64 OLED is drawn in the terminal with
braille characters and the 8 WS2812 LEDs as truecolor dots.

Usage (needs: pip install pillow psutil):
    python3 code/sim.py

Keys:  1 = SW1 (toggle sleep)   2 = SW2 (next page)   q / Ctrl-C = quit
"""

import os
import sys
import time
import types
import select
import termios
import tty
import threading

CODE_DIR = os.path.abspath(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(CODE_DIR, "assets")


# --------------------------------------------------------------------------- #
#  Shared simulator state (talks to the fake hardware below)                   #
# --------------------------------------------------------------------------- #
class Sim:
    def __init__(self):
        self.lock = threading.Lock()
        self.oled_img = None          # latest PIL image pushed by the OLED
        self.leds = [(0, 0, 0)] * 8   # latest LED colors
        self.brightness = 1.0
        self._press_until = {1: 0.0, 2: 0.0}
        self.running = True

    # --- switches -------------------------------------------------------- #
    def press(self, sw: int):
        # Hold "pressed" briefly so main's 50 Hz rising-edge detector sees it.
        self._press_until[sw] = time.time() + 0.08

    def is_pressed(self, sw: int) -> bool:
        return time.time() < self._press_until[sw]

    # --- rendering ------------------------------------------------------- #
    def render(self):
        with self.lock:
            frame = ["\x1b[H"]  # cursor home (avoid full clear to limit flicker)
            frame.append("TRSID simulator  [1]=SW1 sleep  [2]=SW2 next  [q]=quit\x1b[K\n")
            frame.append("\x1b[97m+" + "-" * 64 + "+\x1b[K\n")
            for line in self._oled_lines():
                frame.append("\x1b[97m|" + line + "|\x1b[0m\x1b[K\n")
            frame.append("\x1b[97m+" + "-" * 64 + "+\x1b[0m\x1b[K\n")
            frame.append("LEDs: " + self._led_str() + "\x1b[K\n")
            sys.stdout.write("".join(frame))
            sys.stdout.flush()

    def _oled_lines(self):
        if self.oled_img is None:
            return [" " * 64 for _ in range(16)]
        px = self.oled_img.load()
        w, h = self.oled_img.size
        # 2x4 pixels per braille cell -> 64 wide x 16 tall for a 128x64 panel.
        dots = [(0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04), (1, 0, 0x08),
                (1, 1, 0x10), (1, 2, 0x20), (0, 3, 0x40), (1, 3, 0x80)]
        lines = []
        for by in range(0, h, 4):
            row = []
            for bx in range(0, w, 2):
                bits = 0
                for dx, dy, val in dots:
                    if px[bx + dx, by + dy]:
                        bits |= val
                row.append(chr(0x2800 + bits))
            lines.append("".join(row))
        return lines

    def _led_str(self):
        out = []
        for (r, g, b) in self.leds:
            r = int(r * self.brightness)
            g = int(g * self.brightness)
            b = int(b * self.brightness)
            out.append(f"\x1b[38;2;{r};{g};{b}m●")
        return " ".join(out) + "\x1b[0m"


SIM = Sim()


# --------------------------------------------------------------------------- #
#  Fake hardware modules (installed into sys.modules before importing main)    #
# --------------------------------------------------------------------------- #
def _install_fakes():
    board = types.ModuleType("board")
    board.D18 = "D18"
    board.SCL = "SCL"
    board.SDA = "SDA"

    busio = types.ModuleType("busio")

    class I2C:
        def __init__(self, *a, **k):
            pass
    busio.I2C = I2C

    neopixel = types.ModuleType("neopixel")
    neopixel.GRB = "GRB"
    neopixel.RGB = "RGB"

    class NeoPixel:
        def __init__(self, pin, n, brightness=1.0, auto_write=True, pixel_order="GRB"):
            self._n = n
            self._buf = [(0, 0, 0)] * n
            SIM.brightness = brightness

        def __len__(self):
            return self._n

        def __setitem__(self, i, color):
            self._buf[i] = tuple(color)

        def fill(self, color):
            self._buf = [tuple(color)] * self._n

        def show(self):
            SIM.leds = list(self._buf)
            SIM.render()
    neopixel.NeoPixel = NeoPixel

    ssd = types.ModuleType("adafruit_ssd1306")

    class SSD1306_I2C:
        def __init__(self, w, h, i2c, addr=0x3C):
            from PIL import Image
            self.width, self.height = w, h
            self._img = Image.new("1", (w, h))

        def fill(self, color):
            from PIL import Image
            self._img = Image.new("1", (self.width, self.height), color)

        def text(self, *a, **k):
            pass  # main draws via PIL + image(); text() is unused there

        def image(self, img):
            self._img = img

        def show(self):
            SIM.oled_img = self._img.copy()
            SIM.render()
    ssd.SSD1306_I2C = SSD1306_I2C

    smbus2 = types.ModuleType("smbus2")

    class SMBus:
        def __init__(self, bus):
            pass

        def write_byte(self, addr, val):
            pass

        def read_byte(self, addr):
            # PCF8574: pin LOW = pressed. Start all-high, clear pressed bits.
            data = 0xFF
            if SIM.is_pressed(1):
                data &= ~0x01
            if SIM.is_pressed(2):
                data &= ~0x02
            return data & 0xFF

        def close(self):
            pass
    smbus2.SMBus = SMBus

    for name, mod in [("board", board), ("busio", busio), ("neopixel", neopixel),
                      ("adafruit_ssd1306", ssd), ("smbus2", smbus2)]:
        sys.modules[name] = mod


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #
def main():
    sys.path.insert(0, CODE_DIR)
    _install_fakes()
    # main.py opens "../assets/*.png"; chdir into the assets dir so that
    # "../assets" resolves back to it.
    os.chdir(ASSETS_DIR)

    import main  # noqa: E402  (must come after fakes are installed)

    # Mac has no thermal/fan sysfs, so feed pages 3 & 4 simulated values.
    main.get_temperature = lambda: 48.0 + 12.0 * abs((time.time() % 20) / 10 - 1)
    main.get_fan_speed = lambda: int(2800 + 1500 * abs((time.time() % 20) / 10 - 1))

    worker = threading.Thread(target=main.main, daemon=True)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sys.stdout.write("\x1b[2J\x1b[?25l")  # clear screen, hide cursor
    sys.stdout.flush()
    try:
        tty.setcbreak(fd)
        worker.start()
        while SIM.running:
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch = sys.stdin.read(1)
                if ch == "1":
                    SIM.press(1)
                elif ch == "2":
                    SIM.press(2)
                elif ch in ("q", "Q", "\x03"):  # q or Ctrl-C
                    break
    except KeyboardInterrupt:
        pass
    finally:
        SIM.running = False
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\n")  # show cursor
        sys.stdout.flush()


if __name__ == "__main__":
    main()
