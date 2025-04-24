/**
 * Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/spi.h"
#include "hardware/gpio.h"

/* Example code to talk to a LAN8651 10BASE-T1S Ethernet PHY via SPI.

   NOTE: The LAN8651 operates at 3.3V levels. Ensure your microcontroller's GPIO
   (and therefore SPI) is compatible with 3.3V levels.

   Connections on Raspberry Pi Pico board to LAN8651:
   (Note: Other boards may have different pin mappings)

   GPIO  2 (pin  4) SCK/spi0_sclk  -> SCLK on LAN8651
   GPIO  3 (pin  5) MOSI/spi0_tx   -> SDI  on LAN8651 (PHY input)
   GPIO  4 (pin  6) MISO/spi0_rx   -> SDO  on LAN8651 (PHY output)
   GPIO  5 (pin  7) Chip select    -> CS_N on LAN8651
   GPIO  0 (pin 17) Reset control  -> RESET_N on LAN8651
   3.3v (pin 36)    -> VDDIO on LAN8651 (I/O power)
   Other power pins should be connected as per LAN8651 datasheet
   GND (pin 38)     -> GND on LAN8651

   For full details on the LAN8651 SPI protocol and register set, refer to:
   Microchip LAN8651 Datasheet (DS00003793)
   https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/LAN8650-LAN8651-Data-Sheet-DS00003793.pdf
*/

// Pin Definitions
#define SCK_PIN   2
#define MOSI_PIN  3
#define MISO_PIN  4
#define CS_PIN    5
#define RST_PIN   0

// Control-Header Bitfields
#define DNC    0x80000000  // data/control selector
#define HDRB   0x40000000  // header bit
#define WNR    0x20000000  // 1=read, 0=write
#define AID    0x10000000  // auto-increment
#define MMS_SH 24          // page selector shift

// MMD registers in MMS 0
#define MMDCTRL 0xFF0D
#define MMDAD   0xFF0E
#define MMDDATA 0xFF0F

// SPI instance
#define SPI_INST spi0

// Function prototypes
uint16_t read_u16(uint8_t mms, uint16_t addr);
uint32_t read_u32(uint8_t mms, uint16_t addr);
void read_bytes(uint8_t mms, uint16_t addr, uint8_t *data, uint8_t length);

// Helper macros for CS control
static inline void cs_select() {
    asm volatile("nop \n nop \n nop");
    gpio_put(CS_PIN, 0);
    asm volatile("nop \n nop \n nop");
}

static inline void cs_deselect() {
    asm volatile("nop \n nop \n nop");
    gpio_put(CS_PIN, 1);
    asm volatile("nop \n nop \n nop");
}

// Updated SPI initialization with proper mode
void init_spi() {
    spi_init(SPI_INST, 500 * 1000); // Start with slower 500kHz
    spi_set_format(SPI_INST, 
                  8,               // 8 bits per transfer
                  SPI_CPOL_1,      // Clock polarity = 1 (try both 0 and 1)
                  SPI_CPHA_1,      // Clock phase = 1 (try both 0 and 1)
                  SPI_MSB_FIRST);  // MSB first
    gpio_set_function(SCK_PIN, GPIO_FUNC_SPI);
    gpio_set_function(MOSI_PIN, GPIO_FUNC_SPI);
    gpio_set_function(MISO_PIN, GPIO_FUNC_SPI);
}

void reset_phy() {
    gpio_put(RST_PIN, 0);
    sleep_ms(100);  // Longer reset pulse
    gpio_put(RST_PIN, 1);
    sleep_ms(500);  // Extended post-reset delay
    
    // Verify reset completed
    uint16_t status = read_u16(0, 0x0008); // OA_STATUS0
    printf("Reset status: 0x%04X\n", status);
}

void build_header(uint8_t mms, uint16_t addr, uint8_t length, uint8_t is_read, uint8_t *buf) {
    /* Build a 32-bit control header for access to (mms, addr). */
    uint32_t lf = ((length - 1) & 0x7F) << 1;
    uint32_t h = DNC | HDRB | AID;
    
    if (is_read) {
        h |= WNR;
    }
    
    h |= (mms << MMS_SH) | (addr << 8) | lf | 0x1;
    
    // Convert to big-endian bytes
    buf[0] = (h >> 24) & 0xFF;
    buf[1] = (h >> 16) & 0xFF;
    buf[2] = (h >> 8) & 0xFF;
    buf[3] = h & 0xFF;
}

void debug_header(uint8_t mms, uint16_t addr, uint8_t length, uint8_t is_read) {
    uint8_t hdr[4];
    build_header(mms, addr, length, is_read, hdr);
    printf("Header for mms=%d, addr=0x%04X: %02X %02X %02X %02X\n",
           mms, addr, hdr[0], hdr[1], hdr[2], hdr[3]);
}

void write_bytes(uint8_t mms, uint16_t addr, uint8_t *data, uint8_t length) {
    /* Write raw bytes to (mms, addr). */
    uint8_t header_buf[4];
    uint8_t tx_buf[4 + length];
    
    build_header(mms, addr, length, 0, header_buf);
    memcpy(tx_buf, header_buf, 4);
    memcpy(tx_buf + 4, data, length);
    
    cs_select();
    spi_write_blocking(SPI_INST, tx_buf, 4 + length);
    cs_deselect();
    sleep_us(10);
}

// Enhanced read_bytes with better timing
void read_bytes(uint8_t mms, uint16_t addr, uint8_t *data, uint8_t length) {
    uint8_t header_buf[4];
    uint8_t rx_buf[4 + length];
    
    build_header(mms, addr, length, 1, header_buf);
    
    cs_select();
    // Add small delay after CS assert
    sleep_us(10);
    
    spi_write_blocking(SPI_INST, header_buf, 4);
    // Add delay between header and data read
    sleep_us(10);
    
    // Read the echoed header and actual data
    spi_read_blocking(SPI_INST, 0, rx_buf, 4 + length);
    
    // Add small delay before CS deassert
    sleep_us(10);
    cs_deselect();
    
    memcpy(data, rx_buf + 4, length);
}

uint16_t read_u16(uint8_t mms, uint16_t addr) {
    uint8_t data[2];
    read_bytes(mms, addr, data, 2);
    return (data[0] << 8) | data[1];
}

uint16_t read_u16_verified(uint8_t mms, uint16_t addr) {
    uint16_t val1 = read_u16(mms, addr);
    uint16_t val2 = read_u16(mms, addr);
    
    if (val1 != val2) {
        printf("Read unstable: 0x%04X vs 0x%04X\n", val1, val2);
        return 0xFFFF;
    }
    return val1;
}

uint32_t read_u32(uint8_t mms, uint16_t addr) {
    uint8_t data[4];
    read_bytes(mms, addr, data, 4);
    return (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3];
}

void health_check() {
    // MMS 0: OA registers
    printf("\n=== LAN8651 Health (MMS 0) ===\n");
    const char *names[] = {"OA_ID", "OA_STATUS0", "OA_BUFSTS", "OA_IMASK0"};
    uint16_t addrs[] = {0x0000, 0x0008, 0x000B, 0x000C};
    
    for (int i = 0; i < 4; i++) {
        uint16_t v = read_u16(0, addrs[i]);
        printf("%-10s (0x%04X): 0x%04X\n", names[i], addrs[i], v);
    }

    // MMS 1: MAC address
    uint32_t hi = read_u32(1, 0x0022);   // MAC_SAB1
    uint16_t lo = read_u16(1, 0x0023);   // MAC_SAT1
    uint8_t mac[6] = {
        (hi >> 24) & 0xFF,
        (hi >> 16) & 0xFF,
        (hi >>  8) & 0xFF,
        hi         & 0xFF,
        (lo >>  8) & 0xFF,
        lo         & 0xFF,
    };
    
    printf("\n=== LAN8651 MAC (MMS 1) ===\n");
    printf("MAC = %02X:%02X:%02X:%02X:%02X:%02X\n", 
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    // Vendor-specific IDs
    uint16_t midver = read_u16(4, 0xCA00);
    uint32_t devid = read_u32(10, 0x0094);
    
    printf("\n=== LAN8651 Vendor IDs ===\n");
    printf("MIDVER = 0x%04X\n", midver);
    printf("DEVID  = 0x%08X\n", devid);
}

// Updated MMD register read with proper delays
uint16_t read_mmd_reg(uint8_t devad, uint16_t reg_addr) {
    uint16_t ctrl;
    uint8_t data[2];
    
    // Address phase
    ctrl = (0 << 14) | (devad & 0x1F);
    data[0] = ctrl >> 8;
    data[1] = ctrl & 0xFF;
    write_bytes(0, MMDCTRL, data, 2);
    sleep_us(10);
    
    // Register address
    data[0] = reg_addr >> 8;
    data[1] = reg_addr & 0xFF;
    write_bytes(0, MMDAD, data, 2);
    sleep_us(10);

    // Data phase
    ctrl = (1 << 14) | (devad & 0x1F);
    data[0] = ctrl >> 8;
    data[1] = ctrl & 0xFF;
    write_bytes(0, MMDCTRL, data, 2);
    sleep_us(10);

    return read_u16(0, MMDDATA);
}

void read_phy_id_mmd() {
    // PHY MMD device address is always 1
    uint16_t p1 = read_mmd_reg(1, 0x02);   // PHY_ID1
    uint16_t p2 = read_mmd_reg(1, 0x03);   // PHY_ID2
    
    printf("PHY_ID1 = 0x%04X, PHY_ID2 = 0x%04X\n", p1, p2);
    printf(" → OUI      = 0x%06X   (should be 0x02003C)\n", (p1 << 2) | (p2 >> 14));
    printf(" → Model    = %02X\n", (p2 >> 4) & 0x3F);
    printf(" → Revision = %d\n", p2 & 0x0F);
}

// Updated PHY ID reading with better bit extraction
void read_phy_id() {
    uint16_t p1 = read_u16(0, 0xFF02);
    uint16_t p2 = read_u16(0, 0xFF03);
    uint32_t phyid = (p1 << 16) | p2;
    
    // Correct OUI extraction per IEEE 802.3
    uint32_t oui = ((p1 & 0x3FF) << 12) | ((p2 >> 4) & 0xFFF);
    uint8_t model = (p2 >> 4) & 0x3F;
    uint8_t rev = p2 & 0x0F;
    
    printf("PHYID raw32 = 0x%08X\n", phyid);
    printf(" → OUI      = 0x%06X   (expect 0x02003C)\n", oui);
    printf(" → Model    = %02X\n", model);
    printf(" → Revision = %01X\n", rev);
}

int main() {
    stdio_init_all();
    sleep_ms(2000);  // Allow time for serial connection
    
    printf("\nLAN8651 Initialization\n");
    printf("======================\n");
    
    // Initialize GPIOs first
    gpio_init(CS_PIN);
    gpio_set_dir(CS_PIN, GPIO_OUT);
    gpio_put(CS_PIN, 1);  // Deselect
    
    gpio_init(RST_PIN);
    gpio_set_dir(RST_PIN, GPIO_OUT);
    gpio_put(RST_PIN, 1);  // Release reset
    
    // Initialize SPI with verification
    init_spi();
    printf("SPI initialized at 500kHz\n");
    
    // Perform reset sequence
    reset_phy();
    
    // Debug first read attempt
    debug_header(0, 0xFF02, 2, 1); // PHY_ID1
    uint16_t phy_id1 = read_u16_verified(0, 0xFF02);
    printf("PHY_ID1 first read: 0x%04X\n", phy_id1);

    // Verify communication
    printf("Reading PHY ID...\n");
    read_phy_id();
    read_phy_id_mmd();

    // 2) PHY soft-reset via OA_RESET (MMS 0, addr 0x0003)
    printf(">>> PHY software reset\n");
    uint8_t reset_cmd[] = {0x01, 0x00};
    write_bytes(0, 0x0003, reset_cmd, 2);
    sleep_ms(100);

    // 3) Enable MAC TX/RX via MAC_NCR (MMS 1, addr 0x0000, bits TXEN|RXEN = 0x0C00)
    printf(">>> Enabling MAC TX+RX\n");
    uint8_t enable_cmd[] = {0x0C, 0x00};
    write_bytes(1, 0x0000, enable_cmd, 2);
    sleep_ms(50);

    // Main monitoring loop
    while (1) {
        printf("\n--- LAN8651 Status ---\n");
        read_phy_id();
        read_phy_id_mmd();
        health_check();
        sleep_ms(5000);
    }

    return 0;
}