import time
import board
import neopixel

PIXEL_PIN = board.D18
NUM_PIXELS = 8
ORDER = neopixel.GRB

datas = [
    (255, 0, 0),  # Red
    (255, 127, 0),  # Orange
    (255, 255, 0),  # Yellow
    (0, 255, 0),  # Green
    (0, 255, 255),  # Cyan
    (0, 0, 255),  # Blue
    (127, 0, 255),  # Purple
    (255, 0, 255),  # Magenta
]

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    NUM_PIXELS,
    brightness=0.5,  # 0.0 to 1.0
    auto_write=False,  # Update by function show()
    pixel_order=ORDER,
)

t = 5

try:
    print("Red")
    pixels.fill((255, 0, 0))
    pixels.show()
    time.sleep(1)
    print("Green")
    pixels.fill((0, 255, 0))
    pixels.show()
    time.sleep(1)
    print("Blue")
    pixels.fill((0, 0, 255))
    pixels.show()
    time.sleep(1)
    print("White at number 0")
    pixels.fill((0, 0, 0))
    pixels[0] = (255, 255, 255)
    pixels.show()
    time.sleep(1)
    print("Motion")
    while t > 0:
        for i in range(NUM_PIXELS):
            for j in range(NUM_PIXELS):
                pixels[j] = datas[(j + i) % NUM_PIXELS]
            pixels.show()
            time.sleep(0.1)
    t -= 1

finally:
    pixels.fill((0, 0, 0))
    pixels.show()
