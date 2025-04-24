from machine import Pin, SPI
import time

# ── Pin Definitions ────────────────────────────────────────────────────────────
SCK_PIN   = 2   # GP2 → SCLK
MOSI_PIN  = 3   # GP3 → SDI (LAN8651 input)
MISO_PIN  = 4   # GP4 → SDO (LAN8651 output)
CS_PIN    = 5   # GP5 → CS_N
RST_PIN   = 0   # GP0 → RESET_N

# ── Control‑Header Bitfields ───────────────────────────────────────────────────
DNC    = 0x80000000  # data/control selector
HDRB   = 0x40000000  # header bit
WNR    = 0x20000000  # 1=read, 0=write
AID    = 0x10000000  # auto‑increment
MMS_SH = 24          # page selector shift

# MMD registers in MMS 0
MMDCTRL = 0xFF0D
MMDAD   = 0xFF0E
MMDDATA = 0xFF0F

def header(mms, addr, length, is_read):
    """Build a 32‑bit control header for access to (mms, addr)."""
    lf = ((length - 1) & 0x7F) << 1
    h = DNC | HDRB | AID
    if is_read:
        h |= WNR
    h |= (mms << MMS_SH) | (addr << 8) | lf | 0x1
    return h.to_bytes(4, 'big')

# ── SPI Setup (mode 0) ─────────────────────────────────────────────────────────
spi = SPI(0,
          baudrate=1_000_000,  # you can increase up to 25 MHz once it's stable
          polarity=0,
          phase=0,
          sck=Pin(SCK_PIN),
          mosi=Pin(MOSI_PIN),
          miso=Pin(MISO_PIN))

cs  = Pin(CS_PIN, Pin.OUT, value=1)
rst = Pin(RST_PIN, Pin.OUT, value=1)

def reset_phy():
    """Toggle the LAN8651 RESET_N pin low→high."""
    rst.value(0)
    time.sleep_ms(50)
    rst.value(1)
    time.sleep_ms(200)

def write_bytes(mms, addr, data):
    """Write raw bytes to (mms, addr)."""
    cs.value(0)
    spi.write(header(mms, addr, len(data), False) + data)
    cs.value(1)
    time.sleep_us(10)

def read_bytes(mms, addr, length):
    """Read `length` bytes from (mms, addr), skipping the 32‑bit echo."""
    cs.value(0)
    spi.write(header(mms, addr, length, True))
    # skip the echoed 32‑bit control header
    spi.read(4)
    # now read the real payload
    data = spi.read(length)
    cs.value(1)
    return data

def read_u16(mms, addr):
    d = read_bytes(mms, addr, 2)
    return (d[0] << 8) | d[1]

def read_u32(mms, addr):
    d = read_bytes(mms, addr, 4)
    return (d[0]<<24)|(d[1]<<16)|(d[2]<<8)|d[3]

def read_phy_id():
    """Read the PHY Identifier registers at MMS 0, addrs 0xFF02/0xFF03."""
    p1 = read_u16(0, 0xFF02)
    p2 = read_u16(0, 0xFF03)
    phyid = (p1 << 16) | p2
    # per IEEE 802.3 clause 22:
    oui   = ((p1 << 2) & 0x000FFC00) | ((p2 >> 14) & 0x000003FF)
    model = (p2 >> 4) & 0x3F
    rev   = p2 & 0x0F
    print(f"PHYID raw32 = 0x{phyid:08X}")
    print(f" → OUI      = 0x{oui:06X}   (expect 0x02003C)")
    print(f" → Model    = {model:02X}")
    print(f" → Revision = {rev:01X}")

def health_check():
    # MMS 0: OA registers
    print("\n=== LAN8651 Health (MMS 0) ===")
    for addr,name in [(0x0000,"OA_ID"),
                      (0x0008,"OA_STATUS0"),
                      (0x000B,"OA_BUFSTS"),
                      (0x000C,"OA_IMASK0")]:
        v = read_u16(0, addr)
        print(f"{name:10} (0x{addr:04X}): 0x{v:04X}")

    # MMS 1: MAC address
    hi = read_u32(1, 0x0022)   # MAC_SAB1
    lo = read_u16(1, 0x0023)   # MAC_SAT1
    mac = [
        (hi >> 24) & 0xFF,
        (hi >> 16) & 0xFF,
        (hi >>  8) & 0xFF,
        hi         & 0xFF,
        (lo >>  8) & 0xFF,
        lo         & 0xFF,
    ]
    print("\n=== LAN8651 MAC (MMS 1) ===")
    print("MAC = %02X:%02X:%02X:%02X:%02X:%02X" % tuple(mac))

    # Vendor‑specific IDs
    midver = read_u16(4, 0xCA00)
    devid  = read_u32(10, 0x0094)
    print("\n=== LAN8651 Vendor IDs ===")
    print(f"MIDVER = 0x{midver:04X}")
    print(f"DEVID  = 0x{devid:08X}")

def read_mmd_reg(devad, reg_addr):
    """
    Perform a Clause-22/MMD read of register `reg_addr` in MMD device `devad`.
    Returns a 16‑bit word.
    """
    # 1) select the MMD address pointer
    #    function=0 (address), DEVAD=<devad>
    ctrl = (0 << 14) | (devad & 0x1F)
    write_bytes(0, MMDCTRL, ctrl.to_bytes(2, 'big'))
    #    write the register offset
    write_bytes(0, MMDAD, reg_addr.to_bytes(2, 'big'))

    # 2) select data (no post‑increment)
    #    function=1 (data no‑post‑inc), DEVAD=<devad>
    ctrl = (1 << 14) | (devad & 0x1F)
    write_bytes(0, MMDCTRL, ctrl.to_bytes(2, 'big'))

    # 3) read the data back from the DATA register
    return read_u16(0, MMDDATA)

def read_phy_id_mmd():
    # PHY MMD device address is always 1
    p1 = read_mmd_reg(1, 0x02)   # PHY_ID1
    p2 = read_mmd_reg(1, 0x03)   # PHY_ID2
    phyid = (p1 << 16) | p2

    # extract per IEEE 802.3 §22
    oui   = (phyid >> 10) & 0x3FFFFF    # bits [31:10]
    model = (phyid >> 4)  & 0x3F        # bits [9:4]
    rev   =  phyid        & 0x0F        # bits [3:0]

    print(f"PHY_ID1 = 0x{p1:04X}, PHY_ID2 = 0x{p2:04X}")
    print(f" → OUI      = 0x{oui:06X}   (should be 0x02003C)")
    print(f" → Model    = {model:02X}")
    print(f" → Revision = {rev}")

def main():
    # 1) HW reset the PHY
    print(">>> PHY hardware reset")
    reset_phy()
    
    print("Reading _actual_ PHY OUI via MMD …")
    read_phy_id_mmd()

    # 2) PHY soft‑reset via OA_RESET (MMS 0, addr 0x0003)
    print(">>> PHY software reset")
    write_bytes(0, 0x0003, b'\x01\x00')
    time.sleep_ms(100)

    # 3) Enable MAC TX/RX via MAC_NCR (MMS 1, addr 0x0000, bits TXEN|RXEN = 0x0C00)
    print(">>> Enabling MAC TX+RX")
    write_bytes(1, 0x0000, b'\x0C\x00')
    time.sleep_ms(50)

    # 4) Enter perpetual dump loop
    while True:
        read_phy_id()
        print("Reading _actual_ PHY OUI via MMD …")
        read_phy_id_mmd()        
        health_check()
        print("\n--- sleeping 5s ---\n")
        time.sleep(5)

# kick off
if __name__ == "__main__":
    main()
