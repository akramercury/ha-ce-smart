<p align="center">
  <img src="images/logo.png" alt="CE Smart (Local) for Home Assistant" width="520">
</p>

<p align="center">
  <b>Local control of CE Smart (Commercial Electric) Wi-Fi devices in Home Assistant.</b><br>
  No cloud at runtime. No firmware flashing. Power &amp; energy monitoring included.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/badge/iot__class-local__polling-brightgreen.svg" alt="Local polling">
</p>

---

## What this is

The **CE Smart** app (Commercial Electric / Home Depot) is a Tuya-platform app. Its
plugs, switches and bulbs speak Tuya's **local LAN protocol**, so Home Assistant can
talk to them **directly on your network** — the same stock device, no re-flashing, no
soldering, no ESPHome. The device keeps working with the CE Smart app at the same time.

This integration gives you:

- 🔌 **On/off control** of plugs, outlets and multi-gang switches
- ⚡ **Live power, current and voltage** for metering plugs
- 📈 **Cumulative energy (kWh)** wired up for the Home Assistant **Energy Dashboard** — daily / monthly / yearly stats and cost, like the app's energy screen (often better)
- 💡 **Bulbs** — on/off, brightness, colour temperature and colour
- 🧩 **Generic mode** that exposes every datapoint a device reports
- 🖥️ **100% local** — survives internet outages, no polling of any cloud

> **Not firmware flashing.** This talks to the device over your LAN using its *local key*.
> Nothing is written to the device. You do **not** run tuya-convert, you do **not** flash
> anything, and you keep the stock firmware and the CE Smart app.

## Requirements

- Home Assistant 2024.12 or newer
- The device on the **same subnet** as Home Assistant, with a **reserved/static IP** (set a DHCP reservation in your router)
- Three values per device: **Device ID**, **Local key**, **IP address**

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/akramercury/ha-ce-smart` as category **Integration**
3. Install **CE Smart (Local)**, then **restart Home Assistant**
4. **Settings → Devices & Services → Add Integration → CE Smart (Local)**

<details>
<summary>Manual install</summary>

Copy `custom_components/ce_smart` into your Home Assistant `config/custom_components/`
directory and restart.
</details>

## Getting your Device ID and Local Key (one time)

Local keys are issued per device and are read from your **own** Tuya account — you are not
extracting anything from the app binary. The standard, documented method:

1. Create a free account at **iot.tuya.com** → *Cloud* → create a Project (Data Center: the
   one for your region, e.g. *Western America* for Canada/US).
2. In the project, **Link Tuya App Account** and scan the QR code **from the CE Smart app**
   (*Me → ⚙ → scan*). Your devices appear under *Devices → Linked by App Account*.
3. Enable the **IoT Core** API for the project.
4. Read each device's **Device ID** and **Local key** from the device list, or run the
   [`tinytuya` wizard](https://github.com/jasonacox/tinytuya#setup-wizard):
   ```bash
   python -m tinytuya wizard
   ```
   which lists every device with its id, local key, IP and protocol version.

> Local keys **rotate** if you remove and re-pair a device in the app. If a device goes
> *unavailable* after re-pairing, grab the new key and update it in the integration.

## Configuration

| Field | Notes |
|------|-------|
| **Name** | Friendly name shown in Home Assistant |
| **Device ID** | 20–22 char id from the step above |
| **Local key** | 16-char key from the step above |
| **IP address** | The device's reserved LAN IP |
| **Protocol version** | Usually `3.3`. Newer firmware: `3.4` / `3.5`. Try another if it won't connect. |
| **Device type** | `Plug/Switch`, `Light`, or `Generic` |

**Polling interval** is adjustable later under the integration's **Configure** button
(default 30 s; 5 s minimum).

## Energy Dashboard

For metering plugs the **Energy (kWh)** sensor is `state_class: total_increasing`, so it
drops straight into **Settings → Dashboards → Energy → Add consumption**. If your particular
model doesn't report a cumulative counter, add a
[Riemann sum integration](https://www.home-assistant.io/integrations/integration/) on the
**Power (W)** sensor and use that instead — same result.

## Supported datapoints

| DP | Meaning | Entity |
|----|---------|--------|
| 1 (and 2, 3…) | relay on/off | Switch |
| 17 | cumulative energy (0.01 kWh) | Energy sensor |
| 18 | current (mA) | Current sensor |
| 19 | power (0.1 W) | Power sensor |
| 20 | voltage (0.1 V) | Voltage sensor |
| 20–24 | bulb switch/mode/brightness/temp/colour | Light |

Generic mode surfaces anything else as sensors so you can identify unknown datapoints.

## Troubleshooting

- **Won't connect** → wrong protocol version is the usual cause; try `3.4`/`3.5`. Confirm the IP and that the device isn't on an isolated IoT VLAN blocked from HA.
- **Goes unavailable after working** → the local key rotated (device re-paired). Update the key.
- **Only one HA poll at a time** → Tuya devices allow few simultaneous local connections; don't run another local-Tuya tool against the same device at a short interval.

## Credits

Built on the excellent [`tinytuya`](https://github.com/jasonacox/tinytuya) local protocol
library. Not affiliated with Commercial Electric, Home Depot or Tuya.

## License

MIT
