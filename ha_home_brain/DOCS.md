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

`language: auto` (default) follows Home Assistant when Vatra has that language, English otherwise.
Set `en`, `ro`, `hu` or `es` to force one.
This decides notifications, the evening digest, approval buttons and the language of the AI agents.
The panel starts in the same language and has a language switch, remembered per browser/phone. Jarvis answers in the language you write to it.

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
- **Not a habit:** something that changes at exactly the same time every day (a device schedule,
  Node-RED, another system) or after exactly the same delay – a person never does that. Changes made by
  Home Assistant system users are ignored too; add the user an AI agent or a script logs in with to
  `learning.ignore_users`.
- **Never for this device** removes a device from habit learning (you can include it again from the
  *Habits* tab).
- **Habit suggestions** (Setup, or `learning.proposals`): `notify` (default), `panel` – only in the
  *Habits* tab, no notifications – or `off` if you write your own automations.

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

## Voice (Assist)

Jarvis can answer by voice through Home Assistant Assist. Install the small **Vatra (voice / Assist)** integration
from HACS (custom repository `https://github.com/RazvanR1/Vatra`, category Integration), restart Home Assistant,
confirm the discovered **Vatra** in Settings → Devices & services, then choose **Vatra Jarvis** as the conversation
agent in Settings → Voice assistants. Details and the manual address/code: panel → Setup → Voice (Assist).

## Vacation mode

Vacation mode turns on by itself when **all people** (`learning.persons`) have been away for `vacation.away_hours`
(default 24), or when you press **Start vacation mode** on the Home tab. While it is on:
- vacation days are left out of habit learning;
- small observations ("left on too long", "silent sensor", "flapping") are muted;
- any motion or door/window opening in the house is sent to your phone right away (`vacation.security_alerts`).

**I'm back** turns it off; it goes back to automatic as soon as someone is home. Also available as
`binary_sensor.vatra_vacation` (MQTT).

## Mode monitor
For systems you built yourself – heating with eco / hybrid / gas / boost modes, a heat pump mode, an
alarm mode. Pick the entities in **Setup → 6** (or `modes.entities`). Vatra only **watches** them, it
never changes them:
- time spent in each mode today and in the last 7 days (*Home* tab, weekly report, Jarvis);
- an alert when a mode switches much more often than usual in the last hour (a threshold or a sensor
  bouncing), or when a mode lasts 1.5× longer than its longest run in the last two weeks.

Statistics come from Home Assistant's history, so they are there from the first start; alerts start
after 3 days of history. `modes.alerts: false` keeps only the statistics.

## Weekly report

On Sunday at the digest hour (`agents.digest_hour`), one message: new habits and automations, actions (and undos),
alerts, observations, clean up and vacation days. The same summary is on the Home tab under **This week**.
Turn it off with `weekly_report: false`.

## Clean up

Every few hours Vatra looks for devices whose entities are **all** unavailable now **and** had no real value in
Home Assistant's history for the last `cleanup.days` days (default 7) – sold devices, deleted Docker containers,
abandoned integrations. Each one appears in **Approvals** (no phone notification): **Disable** turns its entities
off in the entity registry (nothing is deleted), **Keep** means it won't ask again. **Undo** in the Log enables them.

## Vatra entities (MQTT)

If Home Assistant has the **MQTT integration** set up (e.g. with the Mosquitto app), Vatra publishes through it – no passwords needed – and a **Vatra** device appears:

| Entity | What it shows |
|---|---|
| `sensor.vatra_active_alerts` | Number of active alerts; the list is in its attributes |
| `sensor.vatra_pending_approvals` | Requests waiting for your answer |
| `binary_sensor.vatra_problem` | On when a confirmed fault is active |
| `sensor.vatra_last_alert` | Title of the newest alert |
| `sensor.vatra_unusual` | Unusual observations |
| `sensor.vatra_cleanup` | Dead devices that can be disabled |

Example: turn a light red while `binary_sensor.vatra_problem` is on. Turn it off with `mqtt_entities: false`.

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
  # Cloud (optional, needs an API key): OpenAI https://api.openai.com/v1 · Claude https://api.anthropic.com/v1
  model: "qwen3.5:9b"
  num_ctx: 8192        # Ollama: same as the Ollama integration in HA, so the model isn't reloaded
  # extra_body: '{"chat_template_kwargs": {"enable_thinking": false}}'   # OpenAI type: thinking models answer faster
agents:
  agents_interval_hours: 6
  quiet_hours: "23-7"  # agents don't run noisy analyses at night
```

## Security

The panel only answers requests that come through Home Assistant ingress. Data is stored in `/data/brain.db`.
