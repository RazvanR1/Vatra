"""Translations. One language per installation: option `language` (auto | en | ro).
`auto` follows the Home Assistant language: Romanian if HA is in Romanian, English otherwise.

Use: t("key", name="Lamp") -> text in the active language. A missing key falls back to English,
then to the key itself, so a forgotten translation never crashes anything.
To add a language: add a column to every entry below (and to static/i18n in index.html).
"""
from __future__ import annotations

SUPPORTED = ("en", "ro")
_lang = "en"


def set_language(lang: str | None) -> str:
    global _lang
    lang = (lang or "en").lower().replace("_", "-")
    _lang = "ro" if lang.startswith("ro") else "en"
    return _lang


def resolve(option: str | None, ha_language: str | None) -> str:
    """Option `language`: an explicit value wins; `auto` uses the HA language."""
    opt = (option or "auto").lower()
    return set_language(ha_language if opt == "auto" else opt)


def lang() -> str:
    return _lang


def t(key: str, **kw) -> str:
    entry = S.get(key)
    if entry is None:
        text = key
    else:
        text = entry.get(_lang) or entry.get("en") or key
    return text.format(**kw) if kw else text


def _e(en: str, ro: str) -> dict:
    return {"en": en, "ro": ro}


S: dict[str, dict] = {
    # ---------- trepte / context ----------
    "tier.unusual": _e("unusual", "neobișnuit"),
    "tier.anomaly": _e("possible anomaly", "posibilă anomalie"),
    "tier.fault": _e("confirmed fault", "defecțiune confirmată"),
    "ctx.docked": _e("{name} is docked ({state})", "{name} e în bază ({state})"),
    "ctx.home": _e("{name} is home", "{name} e acasă"),
    "ctx.charging": _e("{name} is charging", "{name} se încarcă"),
    "ctx.still": _e("{name} is not moving", "{name} stă pe loc"),
    "ctx.state": _e("{name}: {state}", "{name}: {state}"),
    "ctx.task_sensor": _e("the device works; this sensor only has a value during an activity",
                          "dispozitivul funcționează; senzorul are valoare doar în timpul unei activități"),
    "ctx.running": _e("{name}: running", "{name}: funcționează"),
    "ctx.on": _e("{name}: on", "{name}: pornit"),
    "ctx.flaky": _e("often drops out and recovers on its own – normal for it",
                    "pică des și își revine singur – comportament obișnuit"),
    "ctx.device_alive": _e("the rest of the device works", "restul dispozitivului funcționează"),
    "ctx.running_now": _e("Running now: {loads}", "Funcționează acum: {loads}"),
    "ctx.no_heavy_loads": _e("no large loads", "niciun consumator mare"),
    "ctx.bulb_feed": _e("relay that powers smart bulbs (on ≠ light lit)",
                        "releu de alimentare becuri smart (pornit ≠ lumină aprinsă)"),
    "ctx.same_device": _e("same device: {rel}", "același dispozitiv: {rel}"),

    # ---------- paznic ----------
    "guard.unavailable": _e("Device unavailable", "Dispozitiv indisponibil"),
    "guard.no_value": _e("Sensor without value", "Senzor fără valoare"),
    "guard.battery": _e("Low battery", "Baterie slabă"),
    "guard.alert": _e("Alert", "Alertă"),
    "guard.down_msg": _e("{name} has been {state} for {minutes} minutes",
                         "{name} e {state} de {minutes} minute"),
    "guard.battery_msg": _e("{name}: battery {level}%.", "{name}: baterie {level}%."),
    "guard.burst_title": _e("Several devices down", "Mai multe dispozitive picate"),
    "guard.burst_msg": _e("{count} devices: {names}{more}.", "{count} dispozitive: {names}{more}."),
    "guard.and_more": _e(" and {n} more", " și încă {n}"),
    "guard.ok_again": _e("{name} is fine again.", "{name} e din nou în regulă."),
    "resolved": _e("Resolved: {title}", "Rezolvat: {title}"),

    # ---------- notificări ----------
    "notify.batch_title": _e("Vatra: {n} things to check", "Vatra: {n} lucruri de verificat"),
    "notify.batch_more": _e("…and {n} more in the panel", "…și încă {n} în panou"),
    "notify.channel": _e("Vatra", "Vatra"),
    "notify.channel_urgent": _e("Vatra – urgent", "Vatra – urgent"),
    "digest.title": _e("Vatra – daily summary", "Vatra – rezumatul zilei"),
    "digest.more": _e("…and {n} more", "…și încă {n}"),
    "digest.guard": _e("• Guard: {n} to check (e.g. {example})", "• Paznic: {n} de verificat (ex. {example})"),
    "digest.unusual": _e("• Unusual: {n} observations (e.g. {example})",
                         "• Neobișnuit: {n} observații (ex. {example})"),

    # ---------- neobișnuit ----------
    "an.range_title": _e("Unusual value", "Valoare neobișnuită"),
    "an.high": _e("high", "mare"),
    "an.low": _e("low", "mică"),
    "an.range_msg": _e("{name} reads {value}{unit}, unusually {dir} for this hour "
                       "(usually {mean}{unit}, between {lo} and {hi}).",
                       "{name} arată {value}{unit}, neobișnuit de {dir} pentru ora asta "
                       "(de obicei {mean}{unit}, între {lo} și {hi})."),
    "an.silent_title": _e("Silent sensor", "Senzor tăcut"),
    "an.silent_msg": _e("{name} has not reported for {dur} (usually ~{rate} times per hour).",
                        "{name} n-a mai raportat de {dur} (de obicei de ~{rate} ori pe oră)."),
    "an.open": _e("open", "deschis(ă)"),
    "an.on": _e("on", "pornit(ă)"),
    "an.dwell_title": _e("In this state for too long", "Stă prea mult așa"),
    "an.dwell_msg": _e("{name} has been {state} for {dur}; usually at most {limit}.",
                       "{name} e {state} de {dur}; de obicei cel mult {limit}."),
    "an.flap_title": _e("Keeps switching on and off", "Se aprinde și se stinge întruna"),
    "an.flap_msg": _e("{name} changed state {n} times in 15 min (usual maximum: {max}).",
                      "{name} și-a schimbat starea de {n} ori în 15 min (maxim obișnuit: {max})."),
    "an.away_title": _e("House open, nobody home", "Casă deschisă, nimeni acasă"),
    "an.away_msg": _e("Nobody is home, but these are open: {items}.",
                      "Nu e nimeni acasă, dar e deschis: {items}."),
    "dur.min": _e("{n} min", "{n} min"),
    "dur.h": _e("{n} h", "{n} h"),
    "dur.hm": _e("{h} h {m} min", "{h} h {m} min"),
    "dur.days": _e("{n} days", "{n} zile"),

    # ---------- aprobări / siguranță ----------
    "btn.approve": _e("Approve", "Aprobă"),
    "btn.always": _e("Always", "Mereu"),
    "btn.reject": _e("Reject", "Respinge"),
    "btn.undo": _e("Undo", "Anulează"),
    "btn.seen": _e("Seen", "Am văzut"),
    "btn.mute": _e("Not a problem", "Nu e problemă"),
    "btn.create": _e("Create", "Creează"),
    "btn.not_habit": _e("Not a habit", "Nu e obicei"),
    "btn.yes": _e("Yes", "Da"),
    "btn.no": _e("No", "Nu"),
    "safe.never": _e("{svc} is never allowed", "{svc} nu e permis niciodată"),
    "safe.domain": _e("the entity does not match the service domain",
                      "entitatea nu corespunde domeniului serviciului"),
    "safe.temp_invalid": _e("invalid temperature", "temperatură invalidă"),
    "safe.temp_range": _e("{temp}° is outside the limits {lo}–{hi}°", "{temp}° e în afara limitelor {lo}–{hi}°"),
    "safe.critical": _e("critical action: always needs approval", "acțiune critică: cere mereu aprobare"),
    "ap.gone": _e("The request no longer exists.", "Cererea nu mai există."),
    "ap.nothing": _e("Nothing to do.", "Nimic de făcut."),
    "ap.shadow_log": _e("{src} would have done {svc} on {target}: {reason}",
                        "{src} ar fi făcut {svc} pe {target}: {reason}"),
    "ap.action_log": _e("{src}: {svc} on {target}", "{src}: {svc} pe {target}"),
    "ap.done_title": _e("Done: {what}", "Am făcut: {what}"),
    "ap.no_undo": _e("Nothing to undo.", "Nu am ce anula."),
    "ap.auto_deleted": _e("The automation was deleted.", "Automatizarea a fost ștearsă."),
    "ap.cant_restore": _e("I don't know how to bring {name} back to “{state}”.",
                          "Nu știu cum să readuc {name} la „{state}”."),
    "ap.restored": _e("{name} is back to “{state}”.", "{name} a revenit la „{state}”."),
    "ap.rejected": _e("Rejected; I won't suggest this again.", "Respins; nu mai propun asta."),
    "ap.done": _e("Done.", "Făcut."),
    "ap.already": _e("Already decided.", "Deja decis."),

    # ---------- reguli integrate ----------
    "rule": _e("rule", "regulă"),
    "rule.cameras": _e("Cameras only when nobody is home", "Camere doar când nu e nimeni acasă"),
    "rule.cameras_title": _e("Cameras", "Camere"),
    "rule.cameras_on": _e("Nobody home: cameras on", "Nimeni acasă: camere pornite"),
    "rule.cameras_off": _e("Someone home: cameras off", "Cineva acasă: camere oprite"),
    "rule.boiler": _e("Boiler off while the AC is heating", "Centrală oprită cât încălzește AC-ul"),
    "rule.boiler_off": _e("AC heating: boiler off (was {prev})", "AC încălzește: centrala oprită (era {prev})"),
    "rule.boiler_back": _e("AC no longer heating: boiler back to {mode}",
                           "AC nu mai încălzește: centrala revine pe {mode}"),
    "rule.valves": _e("Radiator valves follow the thermostat", "Robinete urmează termostatul"),
    "rule.valves_set": _e("{names} set to {temp}°", "{names} setat la {temp}°"),
    "rule.disabled": _e("off (an HA automation already does this)",
                        "oprită (o face deja o automatizare din HA)"),

    # ---------- învățare / panou ----------
    "rec.imported": _e("Imported {days} days of history ({n} changes, {num} numeric sensors).",
                       "Am importat istoricul pe {days} zile ({n} schimbări, {num} senzori numerici)."),
    "main.learned": _e("{n} habits found ({covered} already automated) from {tr} changes.",
                       "{n} obiceiuri găsite ({covered} deja automatizate) din {tr} schimbări."),
    "main.habit_title": _e("New habit found", "Obicei nou găsit"),
    "main.habit_msg": _e("{desc} Tested on history: right on {hits} of {fired} days. Create an automation?",
                         "{desc} Testat pe istoric: {hits} din {fired} zile corect. Fac o automatizare?"),
    "main.habit_gone": _e("The habit no longer exists.", "Obiceiul nu mai există."),
    "main.habit": _e("habit", "obicei"),
    "main.learning": _e("Learning", "Învățare"),
    "main.created_log": _e("Created “{alias}”.", "Am creat „{alias}”."),
    "main.created": _e("Created the automation “{alias}”.", "Am creat automatizarea „{alias}”."),
    "main.not_habit": _e("Noted: not a habit, I won't suggest it again.", "Am notat: nu e obicei, nu-l mai propun."),
    "main.muted": _e("I won't flag this for this device anymore.", "Nu mai semnalez asta pentru acest dispozitiv."),
    "main.dwell_more": _e("Got it; next time I'll wait twice as long.",
                          "Am înțeles; data viitoare aștept de două ori mai mult."),
    "main.snoozed": _e("Got it; I won't insist today.", "Am înțeles; nu mai insist azi."),
    "web.ask": _e("Type a question.", "Scrie o întrebare."),
    "web.test": _e("Test notification from Vatra.", "Notificare de test din Vatra."),
    "error.generic": _e("Error: {err}", "Eroare: {err}"),
    "setup.test_sent": _e("Test sent to {svc}. Check the phone.", "Am trimis un test pe {svc}. Uită-te pe telefon."),
    "setup.no_supervisor": _e("Saving needs the Home Assistant Supervisor (Vatra must run as an add-on).",
                              "Salvarea are nevoie de Supervisor-ul Home Assistant (Vatra trebuie să ruleze ca add-on)."),
    "setup.saved": _e("Saved. Vatra restarts with the new settings…", "Salvat. Vatra repornește cu setările noi…"),
    "setup.saved_log": _e("Settings saved from the setup guide.", "Setări salvate din ghidul de pornire."),
    "web.proposed": _e("Sent the proposal to your phone and to Approvals.",
                       "Am trimis propunerea pe telefon și în Aprobări."),
    "web.restored": _e("Back in the list.", "Repus în listă."),
    "web.relearned": _e("Relearned: {n} habits.", "Am reînvățat: {n} obiceiuri."),
    "web.agent_ran": _e("{name}: {n} observations.", "{name}: {n} observații."),
    "llm.not_configured": _e("The AI model is not configured.", "Modelul AI nu e configurat."),

    # ---------- obiceiuri ----------
    "hab.days.weekday": _e("on weekdays", "în zilele lucrătoare"),
    "hab.days.weekend": _e("on weekends", "în weekend"),
    "hab.days.all": _e("every day", "zilnic"),
    "hab.verb.on": _e("you turn on", "pornești"),
    "hab.verb.off": _e("you turn off", "oprești"),
    "hab.verb.open": _e("you open", "deschizi"),
    "hab.verb.closed": _e("you close", "închizi"),
    "hab.verb.cleaning": _e("you start", "pornești"),
    "hab.verb.docked": _e("you send to the dock", "trimiți la bază"),
    "hab.verb.heat": _e("you set to heating", "pui pe încălzire"),
    "hab.verb.cool": _e("you set to cooling", "pui pe răcire"),
    "hab.verb.set": _e("you set to {state}", "pui pe {state}"),
    "hab.time_desc": _e("{days} around {time} {verb} {name} ({n} of {total} days).",
                        "{days} pe la {time} {verb} {name} ({n} din {total} zile)."),
    "hab.seq_desc": _e("After {a} becomes “{state}”, {verb} {b} within ~{lag} s ({n} of {total} times).",
                       "După ce {a} devine „{state}”, {verb} {b} în ~{lag} s ({n} din {total} ori)."),
    "hab.auto_desc": _e("Created by Vatra from the habit: {desc} Backtest: {hits}/{fired} correct.",
                        "Creat de Vatra din obiceiul: {desc} Backtest: {hits}/{fired} corecte."),

    # ---------- agenți AI ----------
    "agent.climate.name": _e("Climate", "Climă"),
    "agent.climate.task": _e(
        "comfort and heating: temperature and humidity per room, thermostat, AC, windows open while heating "
        "is on, condensation/mould risk (high humidity + low temperature), heating that doesn't heat.",
        "confort și încălzire: temperaturi și umiditate pe camere, termostat, AC, ferestre deschise "
        "cu încălzirea pornită, risc de condens/mucegai (umiditate mare + temperatură scăzută), "
        "încălzire care nu încălzește."),
    "agent.energy.name": _e("Energy", "Energie"),
    "agent.energy.task": _e(
        "energy use: what uses a lot, what was left on for nothing, consumption unusual for a normal day, "
        "concrete ways to save.",
        "consum de energie: ce consumă mult, ce a rămas pornit degeaba, centrala (priza cu măsurare), "
        "consum anormal față de ziua obișnuită, idei concrete de economie."),
    "agent.security.name": _e("Security", "Securitate"),
    "agent.security.task": _e(
        "home safety: who is home, doors, motion, cameras, alarm, water/gas/smoke leaks, activity while "
        "nobody is home, security devices that don't work.",
        "siguranța casei: cine e acasă, uși, mișcare, camere, alarmă, scurgeri de apă/gaz/fum, "
        "activitate când nu e nimeni acasă, dispozitive de securitate care nu funcționează."),
    "agent.server.name": _e("Server & homelab", "Server & homelab"),
    "agent.server.task": _e(
        "homelab health: Proxmox, TrueNAS (pools, disks), stopped Docker containers, disks almost full "
        "(over 85%), disk temperatures over 55°C, available updates.",
        "sănătatea homelab-ului: Proxmox, TrueNAS (pool-uri, discuri), containere Docker oprite, "
        "spațiu pe disc aproape plin (peste 85%), temperaturi de disc peste 55°C, actualizări disponibile."),
    "agent.default_site": _e("an ordinary home", "o casă obișnuită"),
    "agent.climate_line": _e("(set {set}, current {cur}, action {action})",
                             "(setat {set}, actual {cur}, acțiune {action})"),
    "agent.stats": _e("24h: min {mn} mean {mean} max {mx}", "24h: min {mn} medie {mean} max {mx}"),
    "agent.changes": _e("{n} changes/24h", "{n} schimbări/24h"),
    "agent.down": _e("(+ {n} unavailable entities, watched by the guard)",
                     "(+ {n} entități indisponibile, urmărite de paznic)"),
    "agent.open_findings": _e("Open local observations:", "Observații locale deschise:"),
    "agent.actions_yes": _e("You may propose an action only on an entity_id from the data; a human will approve it.",
                            "Poți propune o acțiune doar pe entity_id din date; va fi aprobată de om."),
    "agent.actions_no": _e('Do not propose actions: always set "action": null.',
                           'Nu propune acțiuni: pune mereu "action": null.'),
    "agent.prompt": _e(
        """You are the “{name}” agent of Vatra, the home's local brain. Answer in English, concretely and briefly.
About the home: {site}
Your job: {task}
Below is the data (entity_id | name | state | 24 h statistics | states of other entities of the
same device). Unavailable entities are NOT listed: the guard handles them, do not comment on them.
Strict rules:
- “unavailable”/“unknown” or missing updates do NOT mean a fault: a GPS sitting at home while
  charging, or a robot's mapping sensor while it is not mapping, simply has nothing to report.
- Before any conclusion, check the surrounding entities and the “Running now” list. High consumption
  explained by a running heat pump / boiler / AC is normal; do not report it.
- A relay or plug that powers smart bulbs is always on; that does NOT mean the light is lit.
  Only light.* tells whether a light is on.
- Levels: “info” = merely unusual; “warning” = possible anomaly, confirmed by at least one more
  entity; “critical” = confirmed fault or immediate danger.
- Never propose homeassistant.update_entity, reloads or restarts.
- Use ONLY the numbers in the data. Do not invent causes, guess or assume. If unsure, do not report.
- The name of an automation or sensor does NOT mean that thing happened.
- 40-70°C on server CPUs/disks is normal; report only above 75°C.
- “critical” ONLY for immediate danger: water, gas, smoke, house open while nobody is home, server down.
- At most 3 observations, only what really matters. If everything is normal, return an empty list (that is good).
{actions}
Answer ONLY with JSON:
{{"insights": [{{"title": "...", "detail": "...", "severity": "info|warning|critical",
  "action": null | {{"domain": "...", "service": "...", "entity_id": "...", "data": {{}}}}}}]}}""",
        """Ești agentul „{name}” din Vatra, creierul local al casei. Răspunzi în română, concret și scurt.
Despre casă: {site}
Sarcina ta: {task}
Primești mai jos datele (entity_id | nume | stare | statistici pe 24 h | stările altor entități ale
aceluiași dispozitiv). Entitățile indisponibile NU apar aici: de ele se ocupă paznicul, nu le comenta.
Reguli stricte:
- „unavailable”/„unknown” sau lipsa actualizărilor NU înseamnă defecțiune: un GPS care stă acasă la
  încărcat sau un senzor de cartografiere al robotului care nu cartografiază nu au ce raporta.
- Înainte de orice concluzie verifică entitățile din jur și lista „Funcționează acum”. Un consum mare
  explicat de pompa de căldură / centrală / AC care funcționează e normal; nu-l raporta.
- Un releu sau o priză care alimentează becuri smart e mereu pornit(ă); asta NU înseamnă că lumina e
  aprinsă. Starea luminii o dă doar light.*.
- Treptele: „info” = doar neobișnuit; „warning” = posibilă anomalie, confirmată de cel puțin încă o
  entitate; „critical” = defecțiune confirmată sau pericol imediat.
- Nu propune niciodată homeassistant.update_entity, reload sau reporniri.
- Folosește DOAR cifrele din date. Nu inventa cauze, nu ghici, nu presupune. Dacă nu ești sigur, nu raporta.
- Numele unei automatizări sau al unui senzor NU înseamnă că acel lucru s-a întâmplat.
- Temperaturi de 40-70°C la procesoare/discuri de server sunt normale; nu le raporta decât peste 75°C.
- „critical” DOAR pentru pericol imediat: apă, gaz, fum, casă deschisă când nu e nimeni, server oprit.
- Cel mult 3 observații, doar ce chiar contează. Dacă totul e normal, întoarce lista goală (asta e bine).
{actions}
Răspunde DOAR cu JSON:
{{"insights": [{{"title": "...", "detail": "...", "severity": "info|warning|critical",
  "action": null | {{"domain": "...", "service": "...", "entity_id": "...", "data": {{}}}}}}]}}"""),

    # ---------- Jarvis ----------
    "jarvis.prompt": _e(
        """You are Jarvis, the home assistant inside Vatra. Answer briefly, in the language the user writes in.
About the home: {site}
You get the current state of the home (entity_id | name | state) and, if any, what the home's brain noticed.
Answer from them, directly. If the user asks for an action, put it in "actions".
Answer ONLY with JSON of the form:
{{"reply": "text for the user",
 "actions": [{{"domain": "light", "service": "turn_on", "entity_id": "light.x", "data": {{}}}}]}}
Use only entity_ids from the home state. No actions -> "actions": [].""",
        """Ești Jarvis, asistentul casei din Vatra. Răspunzi scurt, în limba în care ți se scrie (implicit română).
Despre casă: {site}
Primești starea curentă a casei (entity_id | nume | stare) și, dacă există, ce a observat creierul casei.
Răspunde din ele, direct. Dacă utilizatorul cere o acțiune, pune-o în "actions".
Răspunde DOAR cu JSON de forma:
{{"reply": "text pentru utilizator",
 "actions": [{{"domain": "light", "service": "turn_on", "entity_id": "light.x", "data": {{}}}}]}}
Folosește doar entity_id din starea casei. Fără acțiuni -> "actions": []."""),
    "jarvis.off": _e("The assistant is not configured (no AI server set – open Setup in the panel).",
                     "Asistentul nu e configurat (lipsește serverul AI – deschide Configurare în panou)."),
    "jarvis.state": _e("Home state:", "Starea casei:"),
    "jarvis.observed": _e("What the home's brain noticed:", "Ce a observat creierul casei:"),
    "jarvis.no_model": _e("I can't reach the AI model: {err}", "Nu pot contacta modelul AI: {err}"),
    "jarvis.empty": _e("(no answer from the model)", "(fără răspuns de la model)"),
    "jarvis.asked": _e("Asked in chat", "Cerut în chat"),
    "jarvis.pending": _e("{eid}: approval request sent to your phone", "{eid}: am trimis cerere de aprobare pe telefon"),
    "jarvis.done": _e("Done.", "Gata."),
    "jarvis.unexpected": _e("(unexpected answer from the model: {raw})", "(răspuns neașteptat de la model: {raw})"),
}
