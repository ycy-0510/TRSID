import time
import board
import busio
import adafruit_ssd1306

OLED_ADDR = 0x3C

i2c = busio.I2C(board.SCL,board.SDA)

oled = adafruit_ssd1306.SSD1306_I2C(128,64,i2c,addr=OLED_ADDR)

try:
    print("Clearing display...")
    oled.fill(0)
    oled.show()
    time.sleep(1)

    print("Displaying text...")
    oled.text("Hello, World!", 0, 0, 1)
    oled.show()
    time.sleep(2)

    print("Displaying multiple lines...")
    oled.fill(0)
    oled.text("Line 1", 0, 0, 1)
    oled.text("Line 2", 0, 10, 1)
    oled.text("Line 3", 0, 20, 1)
    oled.text("Line 4", 0, 30, 1)
    oled.show()
    time.sleep(2)

    print("Displaying a graphic...")
    oled.fill(0)
    oled.rect(10, 10, 50, 50, 1)
    oled.show()
    time.sleep(2)

    print("Displaying with animation...")
    for i in range(0, 128, 10):
        oled.fill(0)
        oled.text("Moving Text", i, 30, 1)
        oled.show()
        time.sleep(0.1)

finally:
    oled.fill(0)
    oled.show()