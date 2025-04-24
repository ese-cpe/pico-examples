from machine import Pin, SPI, unique_id
import time, ubinascii

# === Constants ===
ENABLE_TRX = False  # Set to True to enable ping/pong communication

SCK_PIN  = 2
MOSI_PIN = 3
MISO_PIN = 4

CS_PIN   = 5
IRQ_PIN  = 6
RST_PIN  = 0

FRAME_HDR = 0xAA
PING = 0x01
PONG = 0x02
BUF_TX = 0x0100
BUF_RX = 0x0200
CMD_RD = 0x03
CMD_WR = 0x02

# === LAN8651 Registers ===
REG_DEV_ID   = 0x0000
REG_DEV_STAT = 0x0004
REG_IRQ_STAT = 0x0008
REG_LINK_STAT = 0x0010
REG_IRQ_MASK = 0x0020
REG_MAC_CFG  = 0x0030

# === SPI Setup ===
def init_spi():
    return SPI(0, baudrate=500_000, polarity=1, phase=1,
               sck=Pin(SCK_PIN), mosi=Pin(MOSI_PIN), miso=Pin(MISO_PIN))

spi = init_spi()
cs = Pin(CS_PIN, Pin.OUT, value=1)
rst = Pin(RST_PIN, Pin.OUT, value=1)
irq = Pin(IRQ_PIN, Pin.IN, Pin.PULL_UP)

# === SPI Register Access ===
def spi_write_reg(addr, val):
    cs.value(0)
    spi.write(bytes([CMD_WR]) + addr.to_bytes(2, 'big') + bytes([val]))
    cs.value(1)
    time.sleep_ms(1)

def spi_read_reg(addr):
    cs.value(0)
    spi.write(bytes([CMD_RD]) + addr.to_bytes(2, 'big'))
    b = spi.read(1)
    cs.value(1)
    print(f"SPI READ 0x{addr:04X} → 0x{b[0]:02X}")
    time.sleep_ms(1)
    return b[0]

# === Reset and Init ===
def reset_and_init():
    rst.value(0)
    time.sleep_ms(100)
    rst.value(1)
    time.sleep_ms(500)
    print("IRQ state after reset:", irq.value())
    spi_write_reg(REG_IRQ_MASK, 0x01)
    spi_write_reg(REG_MAC_CFG, 0x01)
    time.sleep_ms(10)
    ds = spi_read_reg(REG_DEV_STAT)
    ls = spi_read_reg(REG_LINK_STAT)
    print(f"DEV_STAT=0x{ds:02X}, LINK_STAT=0x{ls:02X}")
    return ds != 0xFF

# === Register Dump ===
def read_all_regs():
    regs = {
        0x0000: "DEV_ID",
        0x0030: "MAC_CFG",
        0x0008: "IRQ_STAT",
        0x0020: "IRQ_MASK",
        0x0004: "DEV_STAT",
        0x0010: "LINK_STAT"
    }
    print("==== LAN8651 Registers (Page 0) ====")
    for addr, name in regs.items():
        val = spi_read_reg(addr)
        print(f"{name:10} (0x{addr:04X}): 0x{val:02X}")
    print("====================================")

# === Optional PING/PONG ===
def send_frame(cmd, frm, to, payload=b''):
    frame = bytearray([FRAME_HDR, cmd, frm, to]) + payload
    cs.value(0)
    spi.write(bytes([CMD_WR]) + BUF_TX.to_bytes(2, 'big') + frame)
    cs.value(1)

def receive_frame():
    if irq.value() != 0:
        return None
    cs.value(0)
    spi.write(bytes([CMD_RD]) + BUF_RX.to_bytes(2, 'big'))
    buf = spi.read(32)
    cs.value(1)
    for i in range(len(buf) - 3):
        if buf[i] == FRAME_HDR and buf[i + 1] in (PING, PONG):
            return buf[i + 1], buf[i + 2], buf[i + 3]
    return None

def ping_loop(uid, peer):
    seq = 0
    while True:
        seq += 1
        print(f"[{uid}] → PING {peer}")
        send_frame(PING, uid, peer, b"#%d" % seq)
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 2000:
            r = receive_frame()
            if r and r[0] == PONG and r[2] == uid:
                print(f"[{uid}] ← PONG from {r[1]}")
                break
            time.sleep_ms(50)
        else:
            print(f"[{uid}] NO PONG")
        read_all_regs()
        time.sleep(1)

def pong_loop(uid):
    while True:
        r = receive_frame()
        if r and r[0] == PING and r[2] == uid:
            print(f"[{uid}] ← PING from {r[1]}")
            send_frame(PONG, uid, r[1])
            print(f"[{uid}] → PONG {r[1]}")
        time.sleep_ms(100)

# === Entry Point ===
if __name__ == "__main__":
    uid = int(ubinascii.hexlify(unique_id())[-2:], 16)
    role = 'ping' if (uid & 1) else 'pong'
    peer = 0x77 if role == 'ping' else 0x58
    print(f"UID={uid}, role={role}, peer={peer}")

    if not reset_and_init():
        print("LAN8651 init failed!")
    else:
        print(f"LAN8651 up, role: {role}")
        if ENABLE_TRX:
            if role == 'ping':
                ping_loop(uid, peer)
            else:
                pong_loop(uid)
        else:
            while True:
                read_all_regs()
                time.sleep(2)
