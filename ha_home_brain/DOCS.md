# Vatra – the local brain for Home Assistant

Creierul casei: urmărește ce se întâmplă, învață ce e normal în casa **ta**, îți transformă obiceiurile
în automatizări native Home Assistant, îți spune când ceva e neobișnuit și lasă agenți AI locali
să se gândească la întrebările mai grele. Totul rulează local; AI-ul (Ollama) e folosit doar când merită.

## Cum funcționează

1. **Observă** – înregistrează schimbările de stare (cu originea lor: om, dispozitiv, automatizare sau
   Vatra) și importă la pornire istoricul pe ultimele zile.
2. **Învață local, fără AI** – obiceiuri, valori normale pe oră, cât stă fiecare dispozitiv într-o stare.
3. **Decide** – doar ce e neobișnuit sau nou ajunge la tine sau la agenți.
4. **Gândește** – agenții (Climă, Energie, Securitate, Server & homelab) analizează periodic casa,
   doar dacă s-a schimbat ceva de la ultima analiză.
5. **Acționează sau întreabă** – reguli de siguranță fixe, apoi: doar notează (Shadow), te întreabă
   (Co-pilot) sau face singur, cu buton de Anulare (Autonom).

## Obiceiuri → automatizări

- Se învață **doar din ce faci tu** (din aplicație sau de la întrerupător), nu din ce fac automatizările.
- Două tipuri: de oră („zilele lucrătoare pe la 22:30 aprinzi lampa”) și de secvență
  („după ce se deschide ușa, aprinzi lumina de la intrare”).
- Fiecare obicei e **testat pe istoric** (backtest): în câte zile ar fi făcut automatizarea exact ce ai
  făcut tu și în câte ar fi făcut ceva în plus.
- Citește automatizările tale existente și nu propune ce ai deja.
- Obiceiurile puternice ți le trimite pe telefon (cel mult `max_proposals_per_day` pe zi) cu
  **Creează** / **Nu e obicei**. Restul le găsești în tab-ul *Obiceiuri*.
- Automatizările create au id-ul `home_brain_…` și se pot anula din *Jurnal*.

## Neobișnuit (fără listă de dispozitive)

- valori anormale pentru ora respectivă (ex. temperatură), senzori care au tăcut,
  dispozitive care se aprind și se sting întruna, uși/lumini care stau prea mult așa,
  casă deschisă când nu e nimeni acasă (`open_away`, oprit implicit dacă ai deja automatizare).
- Învață din reacțiile tale: **Am văzut** = așteaptă mai mult data viitoare,
  **Nu e problemă** = nu mai semnalează pentru acel dispozitiv.

## Notificări (V2)

Implicit Vatra scrie puțin pe telefon. Tot ce vede apare oricum în panou.

| Ce | Unde ajunge |
|---|---|
| Critic (apă, gaz, fum, casă deschisă când nu e nimeni, defecțiune confirmată din `open_away`) | imediat, mereu |
| Defecțiune confirmată (tot dispozitivul a picat) | grupat, cel mult o dată la `batch_minutes` |
| Posibilă anomalie / neobișnuit / baterie slabă | panou + rezumatul de seară |
| „Rezolvat” | doar panou (`send_resolved`) |
| Cereri de aprobare (obiceiuri, acțiuni) | individual, cu butoane; noaptea așteaptă dimineața |

```yaml
notifications:
  mode: smart          # smart | all (comportamentul vechi) | critical_only
  quiet_hours: "22-7"
  max_per_day: 4       # mesaje grupate pe zi
  batch_minutes: 120
  send_resolved: false
  cooldown_hours: 12
```

## Context: ce nu mai e tratat ca defecțiune

- Un senzor „unavailable” cât timp restul dispozitivului funcționează → *posibilă anomalie* (panou).
- Dispozitiv în repaus: tracker acasă / la încărcat / nemișcat, robot în bază → normal, fără alertă.
- Senzori de activitate (cartografiere, progres, timp rămas, ciclu) → normal când nu e activitate.
- Entități care pică des și își revin singure → normal pentru ele.
- Consum mare cu pompa de căldură / centrala / AC pornite → explicat.
- Releu care alimentează becuri smart → pornit permanent e normal; lumina o dă `light.*`.

## Siguranță

- `autonomy`: `shadow` | `copilot` (implicit) | `autonomous`; pe domenii cu `autonomy_overrides`,
  de ex. `light:autonomous`.
- **Mereu cu aprobare**: lacăte, alarmă, robinete/valve, porți, și orice dispozitiv important
  (centrală, frigider, server, NAS…).
- **Niciodată**: comenzi shell, scripturi Python, Supervisor, oprire/repornire HA, dezactivare automatizări,
  temperaturi în afara `min_temperature`–`max_temperature`.
- Notificările au butoane (**Aprobă / Mereu / Respinge**, **Anulează** după o acțiune făcută singur).

## Opțiuni importante

```yaml
site_context: "Apartament în Cluj. Locuim Razvan și Hajni, lucrăm L–V 8:00–16:30."
notify_services: [notify.mobile_app_telefon]
learning:
  persons: [person.razvan, person.hajni]   # pentru „doar când e cineva acasă”
assistant:
  ollama_url: "http://IP:11434"
  model: "qwen3.5:9b"
  num_ctx: 8192        # același ca integrarea Ollama din HA, ca modelul să nu se reîncarce
agents:
  agents_interval_hours: 6
  quiet_hours: "23-7"  # agenții nu rulează analize zgomotoase noaptea
```

Paznicul (dispozitive indisponibile, baterii) și Jarvis (chat) funcționează ca înainte.

## Securitate

Panoul răspunde doar cererilor venite prin ingress-ul Home Assistant. Datele stau în `/data/brain.db`.
