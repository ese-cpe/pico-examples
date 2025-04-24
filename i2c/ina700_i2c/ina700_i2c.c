#include <math.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/gpio.h"

#define I2C_PORT i2c0
#define SCL_PIN 17
#define SDA_PIN 16
#define INA700_ADDR 0x44
#define ALERT_PIN 27

// Register addresses
#define REG_CONFIG         0x00
#define REG_SHUNT_VOLTAGE  0x01
#define REG_BUS_VOLTAGE    0x05
#define REG_ALERT_STATUS   0x0B
#define REG_TEMP           0x06
#define REG_CURRENT        0x07
#define REG_POWER          0x08
#define REG_ENERGY         0x09
#define REG_CHARGE         0x0A
#define REG_MANUFACTURER_ID 0x3E

void i2c_init_custom() {
    i2c_init(I2C_PORT, 100 * 1000);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SCL_PIN);
    gpio_pull_up(SDA_PIN);
}

uint16_t read_u16(uint8_t reg) {
    uint8_t buf[2];
    i2c_write_blocking(I2C_PORT, INA700_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, INA700_ADDR, buf, 2, false);
    return (buf[0] << 8) | buf[1];
}

int16_t read_s16(uint8_t reg) {
    uint8_t buf[2];
    i2c_write_blocking(I2C_PORT, INA700_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, INA700_ADDR, buf, 2, false);
    return (int16_t)((buf[0] << 8) | buf[1]);
}

uint32_t read_u24(uint8_t reg) {
    uint8_t buf[3];
    i2c_write_blocking(I2C_PORT, INA700_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, INA700_ADDR, buf, 3, false);
    return (buf[0] << 16) | (buf[1] << 8) | buf[2];
}

uint64_t read_u40(uint8_t reg) {
    uint8_t buf[5];
    i2c_write_blocking(I2C_PORT, INA700_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, INA700_ADDR, buf, 5, false);
    return ((uint64_t)buf[0] << 32) | ((uint64_t)buf[1] << 24) | ((uint64_t)buf[2] << 16) | ((uint64_t)buf[3] << 8) | buf[4];
}

int64_t read_s40(uint8_t reg) {
    uint8_t buf[5];
    i2c_write_blocking(I2C_PORT, INA700_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, INA700_ADDR, buf, 5, false);
    int64_t val = ((int64_t)buf[0] << 32) | ((int64_t)buf[1] << 24) | ((int64_t)buf[2] << 16) | ((int64_t)buf[3] << 8) | buf[4];
    if (val & ((int64_t)1 << 39)) {
        val -= ((int64_t)1 << 40);
    }
    return val;
}

float read_shunt_voltage() {
    return read_s16(REG_SHUNT_VOLTAGE) * 2.5f / 1000.0f; // 2.5 µV/LSB → mV
}

float read_bus_voltage() {
    return read_u16(REG_BUS_VOLTAGE) * 3.125f / 1000.0f; // 3.125 mV/LSB → V
}

void scan_i2c() {
    printf("Scanning I2C bus...\n");
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        if (addr == INA700_ADDR) {
            printf("  - I2C Address: 0x%02X\n", addr);
            break;
        }
    }
}

void read_config() {
    uint16_t val = read_u16(REG_CONFIG);
    printf("INA700 CONFIG = 0x%04X\n", val);
}

void write_config() {
    uint16_t config = (0b100 << 9) | (0b100 << 6) | (0b100 << 3) | (0b111); // 0x0930
    uint8_t buf[3] = {REG_CONFIG, (config >> 8) & 0xFF, config & 0xFF};
    i2c_write_blocking(I2C_PORT, INA700_ADDR, buf, 3, false);
    printf("New config written: 0x%04X\n", config);
}

uint16_t debug_raw_registers() {
    uint16_t bus_raw = read_u16(REG_BUS_VOLTAGE);
    int16_t shunt_raw = read_s16(REG_SHUNT_VOLTAGE);
    printf("Raw bus register: 0x%04X\n", bus_raw);
    printf("Raw shunt register: 0x%04X\n", shunt_raw & 0xFFFF);
    return bus_raw;
}

void read_manufacturer_id() {
    uint16_t mid = read_u16(REG_MANUFACTURER_ID);
    char ascii_str[3] = {(char)((mid >> 8) & 0xFF), (char)(mid & 0xFF), '\0'};
    printf("\033[32mManufacturer ID: 0x%04X ('%s')\033[0m\n", mid, ascii_str);
    
    // Test cases
    /*int16_t test_raw[] = {0x0140, 0xFF9C}; // 320 and -100 in 2's complement
    for (int i = 0; i < 2; i++) {
        float temp_c = test_raw[i] * 0.125f;
        printf("TEST : Raw: 0x%04X \u2192 %.2f \u2192 C\n", test_raw[i], temp_c);
    }*/
}

/*float read_temperature() {
    int16_t raw = read_s16(REG_TEMP);
    float temp_c = raw * 0.125f; // 125 m°C per LSB

    printf("Raw TEMP register: 0x%04X (dec: %d) \u2192 Temp: %.2f \u00B0 C\n", raw & 0xFFFF, raw, temp_c);

    if (temp_c >= -40 && temp_c <= 150) {
        return temp_c;
    } else {
        printf("\033[31mWarning: Invalid die temperature reading!\033[0m\n");
        return -999.0f;
    }
}*/

/*float read_temperature() {
    int16_t raw = read_s16(REG_TEMP);
    
    // Alternative method - handle as 12-bit value
    raw = (raw << 4) >> 4;  // Arithmetic right shift to preserve sign
    
    float temp_c = raw * 0.125f;
    
    // Rest of the function remains the same...
}*/


float read_temperature() {
    // Read temperature register (2's complement, 12-bit value)
    int16_t raw = read_s16(REG_TEMP);
    
    // Mask to get only 12 bits (0x0FFF) and sign-extend if negative
    if (raw & 0x0800) {  // Check if negative (bit 11 set)
        raw |= 0xF000;    // Sign-extend to 16 bits
    } else {
        raw &= 0x0FFF;    // Clear upper bits for positive
    }
    
    float temp_c = raw * 0.125f; // 125 m°C per LSB
    
    printf("Raw TEMP register: 0x%04X (dec: %d) \u2192 Temp: %.2f \u00B0C\n",
       raw & 0xFFFF, raw, temp_c);

    // Validate against INA700's operating range
    if (temp_c >= -40.0f && temp_c <= 150.0f) {
        return temp_c;
    } else {
        printf("\033[31mWarning: Invalid die temperature reading!\033[0m\n");
        return -999.0f;
    }
}

void read_all_registers() {
	float temp = read_temperature();
    float current = read_s16(REG_CURRENT) * 0.00048f; // 480 µA/LSB
    float power = read_u24(REG_POWER) * 0.000096f; // 96 µW/LSB
    float energy = read_u40(REG_ENERGY) * 0.000001536f; // 1.536 mJ/LSB
    float charge = read_s40(REG_CHARGE) * 0.000030f; // 30 µC/LSB

    read_manufacturer_id();
    
    printf("\033[36mCurrent: %.6f A\033[0m\n", current);
    printf("\033[36mPower: %.6f W\033[0m\n", power);
    printf("\033[36mEnergy: %.6f J\033[0m\n", energy);
    printf("\033[36mCharge: %.6f C\033[0m\n", charge);
    printf("---------------------------------------------------------\n");
}

int main() {
    stdio_init_all();
    i2c_init_custom();
    gpio_init(ALERT_PIN);
    gpio_set_dir(ALERT_PIN, GPIO_IN);
    gpio_pull_up(ALERT_PIN);

    scan_i2c();
    write_config();
    sleep_ms(500);
    read_config();
	read_manufacturer_id();

	// Add this to your initialization
	uint16_t config = read_u16(REG_CONFIG);
	if ((config & 0x0007) != 0x0007) {  // Check if temperature measurement is enabled
		printf("Warning: Temperature measurements may not be enabled in config!\n");
	}

    while (true) {
        uint16_t bus_raw = debug_raw_registers();
        
        float shunt_mv = read_shunt_voltage();
        float bus_v = read_bus_voltage();
        bool alert = !gpio_get(ALERT_PIN);

        printf("Bus: %.3f V, Shunt: %.3f mV, ALERT: %s\n", 
               bus_v, shunt_mv, alert ? "YES" : "NO");
        
        if (bus_v > 36 || bus_raw == 0xFFFF) {
            printf("Warning: Invalid bus voltage reading!\n");
        }
        
        float vshunt = shunt_mv / 1000.0f; // in volts
        float rshunt = 0.05f;
        float current = fabs(vshunt / rshunt);
        float power = bus_v * current;

        printf("Bus: %.3f V, Shunt: %.3f mV, Current: %.3f A, Power: %.3f W, ALERT: %s\n",
               bus_v, shunt_mv, current, power, alert ? "YES" : "NO");

        read_all_registers();

        printf("\n\r========================================================================\n\r");
        sleep_ms(3000);
    }
}