import time
from smbus2 import SMBus

I2C_BUS = 1
PCF8574_ADDR = 0x20
SW1_ADDR = 0x01
SW2_ADDR = 0x02

bus = SMBus(I2C_BUS)

try:
    bus.write_byte(PCF8574_ADDR, 0x00) # 0x00 = 111 1111, all pins high
    print("Start reading PCF8574...")
    while True:
        data = bus.read_byte(PCF8574_ADDR)
        sw1 = not (data & SW1_ADDR)  # SW1 is connected to P0
        sw2 = not (data & SW2_ADDR)  # SW2 is connected to P1
        print(f'Raw: {bin(data):>10} | SW1: {sw1}, SW2: {sw2}') # :>10 for right-aligning the binary output
        time.sleep(0.2)
except KeyboardInterrupt:
    bus.close()
    print("Stopped by user.")