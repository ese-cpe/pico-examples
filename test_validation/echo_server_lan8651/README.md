# Echo Server LAN8651 - Quick Start Guide

## Overview
This guide explains how to flash, connect, and test the `echo_server_lan8651` firmware on the Raspberry Pi Pico 2 (RP2350) using a LAN8651 10BASE-T1S Ethernet PHY over SPI.

---

## Flash the Firmware
1. **Prepare the Board:**
   - Press and hold the **BOOTSEL** button on the Raspberry Pi Pico 2.
   - While holding the button, **plug the USB cable** into your computer to power the board.
2. **Upload the Firmware:**
   - A new USB mass storage device (e.g., `RPI-RP2` or `RP2350`) will appear.
   - Drag and drop the `echo_server_lan8651.uf2` file onto the device.
   - The board will reboot automatically after flashing.

---

## Connect to the Serial Console
1. **Find the Serial Port:**
   - On Windows: Open **Device Manager** and find the new COM port.
   - On Linux: Run `dmesg | grep tty` to identify the new device (e.g., `/dev/ttyACM0`).

2. **Open a Terminal Session:**
   - Use **PuTTY**, **TeraTerm**, **screen**, or **minicom**.
   - Serial Settings:
     - **Baudrate:** 115200
     - **Data Bits:** 8
     - **Parity:** None
     - **Stop Bits:** 1
     - **Flow Control:** None

3. **Connect:**
   - Open the terminal and connect to the identified serial port.

---

## Interact with the Zephyr Shell
1. After connection, the system prompt will appear:
   ```
   uart:~$
   ```

2. To check if the LAN8651 Ethernet interface is active, type:
   ```
   net iface
   ```

3. Look for output showing an Ethernet interface (`eth0`) with assigned IP addresses:
   ```
   Interface 0 (eth0)
     Link addr : 00:19:05:00:00:04
     MTU       : 1500
     Link      : Up
     IPv4      : 192.0.2.1
     IPv6      : 2001:db8::1
   ```

   This confirms that the LAN8651 10BASE-T1S Ethernet link over SPI is working properly.

---

## Additional Testing
- **Ping Test:** From your PC, ping the board's IPv4 address:
  ```bash
  ping 192.0.2.1
  ```

- **TCP Echo Test:** You can use telnet to test the TCP echo server:
  ```bash
  telnet 192.0.2.1 4242
  ```

Type text into the telnet session; it will echo back if the server is working correctly.

---

## Summary
| Step | Action |
|:-----|:------|
| 1 | Flash the `.uf2` onto the Pico 2 |
| 2 | Open a terminal at 115200 baud |
| 3 | Type `net iface` to verify Ethernet link |
| 4 | Optionally ping or connect via TCP to test |

---

Happy testing! 🚀

