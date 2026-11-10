# Vatra – the local brain for Home Assistant

> 🇷🇴 Documentație în română: [DOCS.ro.md](https://github.com/RazvanR1/Vatra/blob/main/ha_home_brain/DOCS.ro.md)

Vatra watches what happens in your home, learns what is normal in **your** home, turns your habits
into native Home Assistant automations, tells you when something is unusual and lets local AI agents
think about the harder questions. Everything runs locally; the AI (Ollama or any OpenAI-compatible server) is used only when it's worth it.

## Getting started

Start the add-on and open **Vatra** in the sidebar. The **⚙ Setup** tab opens by itself the first time:

1. **Phones** – the Home Assistant Companion apps it found (`notify.mobile_app_*`). Press **Test** to check.
2. **People** – your `person.*` entities.
3. **AI server** (optional) – press **Search my network**: it looks for Ollama (port 11434) on your
   local network, and for LM Studio (1234) / llama.cpp (8080) on the HA machine. Or type the address and press
   **Test connection**; the model list fills in by itself.
4. **About your home** and **Language**.

**Save and restart Vatra** writes these options for you (same as the Configuration tab) and restarts the add-on.
The advanced options stay in the Configuration tab.

## How it works

1. **Observes** – records state changes (with their origin: person, device, automation or Vatra) and
   imports the last days of history at first start.
2. **Learns locally, without AI** – habits, normal values per hour, how long each device stays in a state.
3. **Decides** – only what is unusual or new reaches you or the agents.
4. **Thinks** – the agents (Climate, Energy, Security, Server & homelab) analyse the home periodically,
   only if something changed since the last analysis.
5. **Acts or asks** – fixed safety rules first, then: only logs (Shadow), asks you (Co-pilot) or acts
   on its own with an Undo button (Autonomous).

## Language

`language: auto` (default) follows Home Assistant: Romanian if HA is in Romanian, English otherwise.
Set `en` or `ro` to force one. This decides notifications, the evening digest, approval buttons and
the language of the AI agents. The panel starts in the same language and has an **EN/RO** switch,
remembered per browser/phone. Jarvis answers in the language you write to it.

## Habits → automations

- Learned **only from what you do** (app or wall switch), never from what automations do.
- Two kinds: time habits ("on weekdays around 22:30 you turn on the lamp") and sequence habits
  ("after the door opens, you turn on the hallway light").
- Every habit is **backtested on history**: on how many days the automation would have done exactly
  what you did, and on how many it would have done something extra.
- It reads your existing automations and doesn't propose what you already have.
- Strong habits are sent to your phone (at most `max_proposals_per_day`) with **Create** /
  **Not a habit**. The rest are in the *Habits* tab.
- Created automations have the id `home_brain_…` and can be undone from the *Log*.

## Unusual (no device lists)

- values abnormal for the time of day, sensors that went silent, devices flapping on/off,
  doors/lights left in a state too long, house open while nobody is home (`open_away`, off by default
  if you already have an automation for it).
- Learns from your answers: **Seen** = wait longer next time, **Not a problem** = stop flagging it
  for that device.

## Notifications

By default Vatra writes very little to your phone. Everything it sees is in the panel anyway.

| What | Where it goes |
|---|---|
| Critical (water, gas, smoke, house open while nobody is home) | immediately, always |
| Confirmed fault (the whole device is down) | grouped, at most once every `batch_minutes` |
| Possible anomaly / unusual / low battery | panel + evening digest |
| "Resolved" | panel only (`send_resolved`) |
| Approval requests (habits, actions) | one by one, with buttons; at night they wait until morning |

```yaml
notifications:
  mode: smart          # smart | all (old behaviour) | critical_only
  quiet_hours: "22-7"
  max_per_day: 4       # grouped messages per day
  batch_minutes: 120
  send_resolved: false
  cooldown_hours: 12
```

Tapping a notification opens the Vatra panel; if requests are waiting, it opens on *Approvals*.

## Context: what is not treated as a fault

- One sensor "unavailable" while the rest of the device works → *possible anomaly* (panel only).
- Device at rest: tracker at home / charging / not moving, robot vacuum docked → normal, no alert.
- Activity sensors (mapping, progress, time remaining, cycle) → normal when there is no activity.
- Entities that often drop out and recover on their own → normal for them.
- High consumption while the heat pump / boiler / AC runs → explained.
- Relay powering smart bulbs → always on is normal; only `light.*` tells if the light is lit.

## Safety

- `autonomy`: `shadow` | `copilot` (default) | `autonomous`; per domain with `autonomy_overrides`,
  e.g. `light:autonomous`.
- **Always with approval**: locks, alarm, valves, gates, and any important device
  (boiler, fridge, server, NAS…).
- **Never**: shell commands, Python scripts, Supervisor, stopping/restarting HA, disabling automations,
  `homeassistant.update_entity`, temperatures outside `min_temperature`–`max_temperature`.
- Notifications have buttons (**Approve / Always / Reject**, **Undo** after something done on its own).

## Important options

```yaml
language: auto
site_context: "Flat in Cluj. Two adults, both working Mon–Fri 8:00–16:30. Heat pump + gas boiler."
notify_services: [notify.mobile_app_phone]
learning:
  persons: [person.alex, person.sam]   # for "only when someone is home"
assistant:
  backend: ollama      # or: openai
  ollama_url: "http://IP:11434"
  # openai_url: "http://IP:1234/v1"   # LM Studio; llama.cpp: http://IP:8080/v1
  # api_key: ""                       # only if the server needs one
  model: "qwen3.5:9b"
  num_ctx: 8192        # Ollama: same as the Ollama integration in HA, so the model isn't reloaded
agents:
  agents_interval_hours: 6
  quiet_hours: "23-7"  # agents don't run noisy analyses at night
```

## Security

The panel only answers requests that come through Home Assistant ingress. Data is stored in `/data/brain.db`.
