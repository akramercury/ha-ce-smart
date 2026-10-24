# CE Smart (Local)

Local control of **CE Smart** (Commercial Electric) Wi-Fi plugs, switches and bulbs —
over your LAN, no cloud at runtime, **no firmware flashing**.

- On/off for plugs and multi-gang switches
- Live **power / current / voltage** for metering plugs
- **Cumulative energy (kWh)** ready for the Energy Dashboard
- Bulbs: brightness, colour temperature, colour
- Generic mode exposes every datapoint

You need each device's **Device ID**, **Local key** and **IP** (read from your own Tuya
account — see the README). Set a DHCP reservation so the IP stays fixed.

After install, restart Home Assistant and add it from **Settings → Devices & Services**.
