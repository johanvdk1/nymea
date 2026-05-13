# nymea Integration for Home Assistant

Adopted from the [Mattes83 nymea integration](https://github.com/Mattes83/nymea), extended to support my maveo box which uses non-standard ports. Ports are now automatically discovered from the device via UPnP/server.xml. My Maveo box also had a slightly different api behaviour, using curly brackets around the class id which inhibited the detection of the maveo stick.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

## Overview

The nymea integration allows you to connect your nymea:core system (including maveo box devices) to Home Assistant. This integration enables you to control and monitor nymea-compatible smart home devices directly from Home Assistant.

### Supported Devices

- **maveo box**: Garage door opener with open/close control and status monitoring
- **Lumi Weather Sensor**: Temperature, humidity, and atmospheric pressure sensor (via nymea:core)
- **Other nymea-compatible devices**: Sensors, switches, and buttons via dynamic mapping

### Features

- **Automatic Discovery**: Devices are automatically discovered via Zeroconf/mDNS
- **Automatic Port Discovery**: All ports are read from the device via UPnP (server.xml) — no manual port configuration needed
- **Push Notifications**: Real-time status updates via WebSocket (no polling)
- **Secure Pairing**: Push-button authentication for secure device pairing
- **Multiple Sensors**: Support for temperature, humidity, pressure, battery, and signal strength sensors
- **Garage Door Control**: Full garage door control with open/close/stop and status monitoring

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL: `https://github.com/johanvdk1/nymea`
5. Select "Integration" as the category
6. Click "Add"
7. Find "nymea" in the integration list and click "Install"
8. Restart Home Assistant

### Manual Installation

1. Download the `nymea` folder from this repository
2. Copy it to your Home Assistant's `custom_components` directory:
   ```
   <config_directory>/custom_components/nymea/
   ```
3. Restart Home Assistant

## Setup

### Prerequisites

- A running nymea:core system (e.g., maveo box)
- Network connectivity between Home Assistant and your nymea device
- Physical access to your nymea device for push-button pairing

### Configuration

#### Automatic Discovery (Recommended)

1. Ensure your nymea device is on the same network as Home Assistant
2. Go to **Settings** → **Devices & Services**
3. Home Assistant should automatically discover your nymea device
4. Click **Configure** on the discovered device
5. Click **Submit** to proceed to pairing
6. Within 30 seconds, press the **yellow/orange button** on the back of your maveo box
7. The device will be added to Home Assistant

#### Manual Setup

If automatic discovery doesn't work:

1. Go to **Settings** → **Devices & Services**
2. Click the **+ Add Integration** button
3. Search for "nymea"
4. Enter your nymea device's IP address or hostname
5. Ports will be automatically discovered from the device
6. Click **Submit**
7. Within 30 seconds, press the **yellow/orange button** on the back of your maveo box
8. The device will be added to Home Assistant

> **Note**: The reset button on the back of the maveo box is recessed and only accessible with a paperclip — do not confuse it with the pairing button.

## Entities

Once configured, the integration will create entities for all connected devices:

### Cover Entities
- **Garage Door**: Open, close and stop control with real-time state monitoring

### Sensor Entities
- Temperature (°C)
- Humidity (%)
- Atmospheric Pressure (hPa)
- Battery Level (%)
- Signal Strength (%)
- maveo-stick firmware version

### Binary Sensor Entities
- Connected status
- Opened / Closed status
- Intermediate position
- Maintenance required
- Firmware update available
- Intruder detected
- Light barrier interrupted

### Switch Entities
- Garage light

### Button Entities
- Intermediate position
- Other device-specific actions

## Troubleshooting

### Device Not Discovered

- Ensure your nymea device and Home Assistant are on the same network
- Check that mDNS/Zeroconf is enabled on your network (some routers block this)
- Try manual setup instead

### Cannot Connect Error

- Verify the IP address is correct
- Check that the nymea:core service is running on your device
- Ensure no firewall is blocking port 80 (UPnP discovery) and the JSON-RPC/WebSocket ports reported by the device

### Pairing Fails

- Ensure you press the yellow/orange button within 30 seconds after clicking Submit
- Verify push-button authentication is enabled on your nymea device
- Try restarting the nymea:core service and attempt pairing again

### Entities Not Updating

- Check the Home Assistant logs for connection errors
- Verify the WebSocket connection is not being blocked
- Restart the integration from **Settings** → **Devices & Services** → **nymea**

### Viewing Logs

To enable debug logging for troubleshooting:

1. Add to your `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.nymea: debug
   ```
2. Restart Home Assistant
3. Check logs in **Settings** → **System** → **Logs**

## Removal

To remove the nymea integration:

1. Go to **Settings** → **Devices & Services**
2. Find the **nymea** integration
3. Click the three dots menu
4. Select **Delete**
5. Confirm the removal

All entities and devices will be removed from Home Assistant. This does not affect your nymea device configuration.

## Support & Contribution

- **Issues**: Report bugs or request features on [GitHub Issues](https://github.com/johanvdk1/nymea/issues)
- **Discussions**: Ask questions in the [Home Assistant Community Forum](https://community.home-assistant.io/)

## License

This project is licensed under the MIT License.

## Credits

- Original integration by [@Mattes83](https://github.com/Mattes83/nymea)
- Based on the [nymea:core](https://nymea.io/) project
- nymea API implementation inspired by [nymea-cli](https://github.com/nymea/nymea-cli)
