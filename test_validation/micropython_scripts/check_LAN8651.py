from machine import Pin, SPI, unique_id
import time
import ubinascii

# === Hardware Pins ===
SCK_PIN, MOSI_PIN, MISO_PIN = 2, 3, 4
CS_PIN, IRQ_PIN, RST_PIN     = 5, 6, 0

# === Protocol Constants ===
FRAME_HDR = 0xAA
PING      = 0x01
PONG      = 0x02
BUF_TX    = 0x0100
BUF_RX    = 0x0200
CMD_RD    = 0x03
CMD_WR    = 0x02

# === Device Setup ===
device_hex = ubinascii.hexlify(unique_id())
DEVICE_ID = int(device_hex[-2:], 16)
# Odd UID acts as ping master, even as pong responder
ROLE = 'ping' if DEVICE_ID & 1 else 'pong'
# Replace with your peer's UID
PEER_UID = 0x77 if ROLE == 'ping' else 0x58
print(f"Device UID: {DEVICE_ID}, Role: {ROLE}, Peer: {PEER_UID}")

# === SPI Setup ===
spi = SPI(0, baudrate=1_000_000, polarity=0, phase=0,
          sck=Pin(SCK_PIN), mosi=Pin(MOSI_PIN), miso=Pin(MISO_PIN))
cs  = Pin(CS_PIN, Pin.OUT, value=1)
rst = Pin(RST_PIN, Pin.OUT, value=1)
irq = Pin(IRQ_PIN, Pin.IN, Pin.PULL_UP)

# === Low-level Register Access ===
def spi_write_reg(addr, val):
    cs.value(0)
    spi.write(bytes([CMD_WR]) + addr.to_bytes(2, 'big') + bytes([val]))
    cs.value(1)

def spi_read_reg(addr):
    cs.value(0)
    spi.write(bytes([CMD_RD]) + addr.to_bytes(2, 'big'))
    result = spi.read(1)[0]
    cs.value(1)
    return result

# === Reset & SPI Check ===
def reset_lan8651():
    rst.value(0)
    time.sleep_ms(100)
    rst.value(1)
    # Give the chip time to initialize
    time.sleep_ms(500)

def spi_operation():
    cr = spi_read_reg(0x0000)
    print(f"CR read = 0x{cr:02X}")
    return cr == 0x00

# === Network Initialization ===
def initialize_network():
    reset_lan8651()
    # 1) Enable interrupt first
    spi_write_reg(0x0002, 0x01)  # IER: RX interrupt
    time.sleep_ms(5)
    # 2) Enable chip
    spi_write_reg(0x0000, 0x01)  # CR: chip enable
    time.sleep_ms(10)
    # 3) PHY normal mode
    spi_write_reg(0x0010, 0x00)  # PHYCR
    time.sleep_ms(5)
    # 4) MAC enable
    spi_write_reg(0x0100, 0x01)  # MACCR
    time.sleep_ms(5)
    # Verify CR bit remains set
    cr2 = spi_read_reg(0x0000)
    print(f"CR post-init = 0x{cr2:02X}")
    return bool(cr2 & 0x01)

# === Frame Helpers ===
def send_frame(cmd, frm, to, payload=b""):
    frame = bytearray([FRAME_HDR, cmd, frm, to]) + payload
    cs.value(0)
    spi.write(bytes([CMD_WR]) + BUF_TX.to_bytes(2, 'big') + frame)
    cs.value(1)

def receive_frame():
    # IRQ low means data ready
    if irq.value() != 0:
        return None
    cs.value(0)
    spi.write(bytes([CMD_RD]) + BUF_RX.to_bytes(2, 'big'))
    buf = spi.read(32)
    cs.value(1)
    for i in range(len(buf) - 3):
        if buf[i] == FRAME_HDR and buf[i+1] in (PING, PONG):
            return buf[i+1], buf[i+2], buf[i+3]
    return None

# === Main Loops ===
def ping_loop():
    print(f"[{DEVICE_ID}] Ping master -> {PEER_UID}")
    seq = 0
    while True:
        seq += 1
        payload = f"#{seq}".encode()
        print(f"[{DEVICE_ID}] -> PING {PEER_UID}")
        send_frame(PING, DEVICE_ID, PEER_UID, payload)
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 2000:
            msg = receive_frame()
            if msg and msg[0] == PONG and msg[2] == DEVICE_ID:
                print(f"[{DEVICE_ID}] <- PONG from {msg[1]}")
                break
            time.sleep_ms(50)
        else:
            print(f"[{DEVICE_ID}] No PONG from {PEER_UID}")
        time.sleep(1)

def pong_loop():
    print(f"[{DEVICE_ID}] Pong responder listening")
    while True:
        msg = receive_frame()
        if msg and msg[0] == PING and msg[2] == DEVICE_ID:
            print(f"[{DEVICE_ID}] <- PING from {msg[1]}")
            send_frame(PONG, DEVICE_ID, msg[1])
            print(f"[{DEVICE_ID}] -> PONG {msg[1]}")
        time.sleep_ms(100)

# === Main ===
if __name__ == '__main__':
    if not spi_operation():
        print("SPI failure - check connections")
    elif not initialize_network():
        print("Init failed - check power/reset")
    else:
        print("LAN8651 online")
        if ROLE == 'ping':
            ping_loop()
        else:
            pong_loop()
