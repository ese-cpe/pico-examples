from machine import I2C, Pin
import time
import struct

INA700_ADDR = 0x44

# Register addresses
REG_CONFIG         = 0x00
REG_SHUNT_VOLTAGE  = 0x01
REG_BUS_VOLTAGE    = 0x05
REG_ALERT_STATUS   = 0x0B

# Additional register addresses (from datasheet)
REG_CURRENT        = 0x07
REG_TEMP           = 0x06
REG_POWER          = 0x08
REG_ENERGY         = 0x09
REG_CHARGE         = 0x0A

REG_MANUFACTURER_ID = 0x3E

ALERT_PIN = Pin(27, Pin.IN, Pin.PULL_UP)
i2c = I2C(0, scl=Pin(17), sda=Pin(16), freq=100000)

def read_u16(reg):
    try:
        raw = i2c.readfrom_mem(INA700_ADDR, reg, 2)
        return (raw[0] << 8) | raw[1]
    except Exception as e:
        print(f"Read U16 Error at reg 0x{reg:02X}: {e}")
        return 0

def read_s16(reg):
    try:
        raw = i2c.readfrom_mem(INA700_ADDR, reg, 2)
        return struct.unpack('>h', raw)[0]
    except Exception as e:
        print(f"Read S16 Error at reg 0x{reg:02X}: {e}")
        return 0

def read_u24(reg):
    try:
        raw = i2c.readfrom_mem(INA700_ADDR, reg, 3)
        return (raw[0] << 16) | (raw[1] << 8) | raw[2]
    except Exception as e:
        print(f"Read U24 Error at reg 0x{reg:02X}: {e}")
        return 0

def read_u40(reg):
    try:
        raw = i2c.readfrom_mem(INA700_ADDR, reg, 5)
        return int.from_bytes(raw, 'big')
    except Exception as e:
        print(f"Read U40 Error at reg 0x{reg:02X}: {e}")
        return 0

def read_s40(reg):
    try:
        raw = i2c.readfrom_mem(INA700_ADDR, reg, 5)
        val = int.from_bytes(raw, 'big')
        if val & (1 << 39):  # check sign bit
            val -= (1 << 40)
        return val
    except Exception as e:
        print(f"Read S40 Error at reg 0x{reg:02X}: {e}")
        return 0


def read_shunt_voltage():
    raw = read_s16(REG_SHUNT_VOLTAGE)
    return raw * 2.5 / 1000  # 2.5 µV/LSB → mV

def read_bus_voltage():
    raw = read_u16(REG_BUS_VOLTAGE)
    return raw * 3.125 / 1000  # 3.125 mV/LSB → V

def scan_i2c():
    print("Scanning I2C bus...")
    devices = i2c.scan()
    for d in devices:
        print(f"  - I2C Address: {hex(d)}")

def read_config():
    val = read_u16(REG_CONFIG)
    print(f"INA700 CONFIG = 0x{val:04X}")

def write_config():
    config = (0b100 << 9) | (0b100 << 6) | (0b100 << 3) | (0b111)  # 0x0930
    buf = bytes([(config >> 8) & 0xFF, config & 0xFF])
    i2c.writeto_mem(INA700_ADDR, REG_CONFIG, buf)
    print(f"New config written: 0x{config:04X}")

def debug_raw_registers():
    bus_raw = read_u16(REG_BUS_VOLTAGE)
    shunt_raw = read_s16(REG_SHUNT_VOLTAGE)
    print(f"Raw bus register: 0x{bus_raw:04X}")
    print(f"Raw shunt register: 0x{(shunt_raw & 0xFFFF):04X}")
    return bus_raw

def read_manufacturer_id():
    mid = read_u16(REG_MANUFACTURER_ID)
    ascii_str = ''.join(chr((mid >> 8) & 0xFF) + chr(mid & 0xFF))
    print(f"\033[32mManufacturer ID: 0x{mid:04X} ('{ascii_str}')\033[0m")
    
    for test_raw in [0x0140, 0xFF9C]:  # 320 and -100 in 2's complement
        temp_raw = struct.unpack(">h", bytes([test_raw >> 8, test_raw & 0xFF]))[0]
        temp_c = temp_raw * 0.125
        print(f"TEST : Raw: 0x{test_raw:04X} → {temp_c:.2f} °C")

    return mid

def read_temperature():
    raw = read_s16(REG_TEMP)  # Already decoded from 2's complement
    temp_c = raw * 0.125  # 125 m°C per LSB

    # Print raw register, signed integer, and final temp
    print(f"Raw TEMP register: 0x{raw & 0xFFFF:04X} (dec: {raw}) → Temp: {temp_c:.2f} °C")

    # Validate reasonable operating range
    if -40 <= temp_c <= 150:
        return temp_c
    else:
        print("\033[31mWarning: Invalid die temperature reading!\033[0m")
        return None


# def read_temperature():
#     raw = read_s16(REG_TEMP)  # Already 2’s complement decoded
#     print(f"Raw TEMP register: 0x{raw & 0xFFFF:04X}")
#     temp_c = raw * 0.125  # 125 m°C/LSB
# 
#     # INA700 operational range is -40°C to +150°C
#     if -40 <= temp_c <= 150:
#         return temp_c
#     else:
#         print("Warning: Invalid die temperature reading!")
#         return None


def read_all_registers():
    current = read_s16(REG_CURRENT) * 0.00048  # 480 µA/LSB
    temp = read_temperature()
    power = read_u24(REG_POWER) * 0.000096     # 96 µW/LSB
    energy = read_u40(REG_ENERGY) * 0.000001536  # 1.536 mJ/LSB
    charge = read_s40(REG_CHARGE) * 0.000030     # 30 µC/LSB

    read_manufacturer_id()
    
    print(f"\033[36mCurrent: {current:.6f} A\033[0m")
    print(f"\033[36mPower: {power:.6f} W\033[0m")
    print(f"\033[36mEnergy: {energy:.6f} J\033[0m")
    print(f"\033[36mCharge: {charge:.6f} C\033[0m")
    print("---------------------------------------------------------")

# ----------------------------
# Main Program
# ----------------------------
if __name__ == "__main__":
    scan_i2c()
    write_config()
    time.sleep(0.5)
    read_config()

    read_manufacturer_id()
    
    while True:
        bus_raw = debug_raw_registers()
        
        shunt_mv = read_shunt_voltage()
        bus_v = read_bus_voltage()
        alert = not ALERT_PIN.value()

        print(f"Bus: {bus_v:.3f} V, Shunt: {shunt_mv:.3f} mV, ALERT: {'YES' if alert else 'NO'}")
        
        if bus_v > 36 or bus_raw == 0xFFFF:
            print("Warning: Invalid bus voltage reading!")
        
        vshunt = shunt_mv / 1000  # in volts
        rshunt = 0.05
        #current = vshunt / rshunt
        current = abs(vshunt / rshunt)
        power = bus_v * current

        print(f"Bus: {bus_v:.3f} V, Shunt: {shunt_mv:.3f} mV, "
              f"Current: {current:.3f} A, Power: {power:.3f} W, ALERT: {'YES' if alert else 'NO'}")

        read_all_registers()

        print("\n\r========================================================================\n\r")
        time.sleep(3)
