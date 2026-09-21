# Pixelblaze for Home Assistant

Custom integration for [Pixelblaze](https://electromage.com/) LED controllers,
built on the native WebSocket protocol (port 81) with a persistent async
connection — no extra libraries, no conflict with the Pixelblaze web UI or
other WebSocket clients.

Unlike earlier community integrations, this one **polls the device**, so
pattern or brightness changes made from the Pixelblaze web UI (or any other
controller) show up in Home Assistant within a few seconds.

## Entities

| Entity | Description |
|---|---|
| `light.<name>` | On/off + dimming (global brightness, not saved to flash) |
| `select.<name>_pattern` | Dropdown of saved patterns |
| `switch.<name>_sequencer` | Shuffle-all sequencer |
| `sensor.<name>_fps` | Render FPS (diagnostic) |
| `sensor.<name>_storage_used` | Filesystem usage % (diagnostic) |
| `number.<name>_var_*` | Auto-created for the active pattern's writable exported variables (e.g. `speed`) |
| `sensor.<name>_*` | Auto-created for read-only exported variables (`score`, `lives`, `level`, `lines`...) |

Variable entities follow the active pattern: when you switch patterns, entities
for variables the new pattern doesn't export become unavailable (delete stale
ones from the entity registry if you want to tidy up). Edge-trigger counter
variables (`cL`, `cRot`, `cDrop`...) are intentionally not exposed.

## Services

```yaml
# Set exported variables on the active pattern
service: pixelblaze.set_vars
data:
  variables:
    speed: 8

# Activate a pattern by name (or id)
service: pixelblaze.set_pattern
data:
  name: Stairs Snake
```

`device_id` is optional unless you have more than one Pixelblaze configured.

## Install

1. HACS → Integrations → ⋮ → **Custom repositories** → add this repo URL,
   category *Integration*.
2. Install **Pixelblaze**, restart Home Assistant.
3. Settings → Devices & services → **Add integration** → Pixelblaze → enter the
   device IP (e.g. `10.69.3.32`).

Options (poll interval, dynamic variable entities) are on the integration's
*Configure* dialog.

## Example automation

```yaml
# Zigbee button starts Snake on the stairs
alias: Stairs game night
triggers:
  - trigger: device
    domain: zha
    device_id: <button>
    type: remote_button_short_press
    subtype: turn_on
actions:
  - action: pixelblaze.set_pattern
    data:
      name: Stairs Snake
  - action: pixelblaze.set_vars
    data:
      variables:
        speed: 6
```

## Notes

- `iot_class: local_push`: commands are instant; state also refreshes on a
  poll (default 5 s) because the Pixelblaze does not push every change.
- Brightness is sent with `save: false` to avoid wearing the ESP32 flash;
  the device reverts to its saved brightness after a reboot.
- Tested on Pixelblaze v3.70 with Home Assistant 2024.11+.
