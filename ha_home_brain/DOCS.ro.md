# Vatra – the local brain for Home Assistant

Creierul casei: urmărește ce se întâmplă, învață ce e normal în casa **ta**, îți transformă obiceiurile
în automatizări native Home Assistant, îți spune când ceva e neobișnuit și lasă agenți AI locali
să se gândească la întrebările mai grele. Totul rulează local; AI-ul (Ollama sau orice server compatibil OpenAI) e folosit doar când merită.

## Primii pași

Pornești add-on-ul și deschizi **Vatra** din bara laterală. Prima dată se deschide singur tab-ul **⚙ Configurare**:

1. **Telefoane** – aplicațiile Home Assistant Companion găsite (`notify.mobile_app_*`). Apeși **Test** ca să verifici.
2. **Persoane** – entitățile `person.*`.
3. **Server AI** (opțional) – apeși **Caută în rețea**: caută Ollama (portul 11434) în rețeaua locală și
   LM Studio (1234) / llama.cpp (8080) pe mașina HA. Sau scrii adresa și apeși **Testează conexiunea**;
   lista de modele se completează singură.
4. **Despre casa ta** și **Limba**.

**Salvează și repornește Vatra** scrie opțiunile în locul tău (la fel ca tab-ul Configuration) și repornește
add-on-ul. Opțiunile avansate rămân în tab-ul Configuration.

## Limba

`language: auto` (implicit) urmează Home Assistant dacă Vatra are limba respectivă, altfel engleză.
Poți forța `en`, `ro`, `hu` sau `es`.
De ea depind notificările, rezumatul de seară, butoanele de aprobare și limba agenților AI. Panoul
pornește în aceeași limbă și are un selector de limbă, ținut minte pe fiecare browser/telefon. Jarvis răspunde în limba în care îi scrii.

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
- **Nu e obicei:** ce se schimbă la exact aceeași oră în fiecare zi (un program din dispozitiv,
  Node-RED, alt sistem) sau după exact aceeași întârziere – un om nu face asta niciodată. Schimbările
  făcute de utilizatorii de sistem ai Home Assistant sunt ignorate și ele; utilizatorul cu care se
  conectează un agent AI sau un script îl treci în `learning.ignore_users`.
- **Niciodată pentru dispozitivul ăsta** scoate un dispozitiv din învățarea obiceiurilor (îl poți
  include din nou din tabul *Obiceiuri*).
- **Sugestii de obiceiuri** (Configurare sau `learning.proposals`): `notify` (implicit), `panel` – doar
  în tabul *Obiceiuri*, fără notificări – sau `off` dacă îți scrii singur automatizările.

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

## Voce (Assist)

Jarvis poate răspunde vocal prin Assist din Home Assistant. Instalezi mica integrare **Vatra (voice / Assist)** din
HACS (custom repository `https://github.com/RazvanR1/Vatra`, categoria Integration), repornești Home Assistant,
confirmi **Vatra** descoperit în Setări → Dispozitive și servicii, apoi alegi **Vatra Jarvis** ca agent de
conversație în Setări → Asistenți vocali. Detalii și adresa/codul pentru varianta manuală: panou → Configurare →
Voce (Assist).

## Mod vacanță

Modul vacanță pornește singur când **toate persoanele** (`learning.persons`) sunt plecate de `vacation.away_hours`
ore (implicit 24) sau când apeși **Pornește modul vacanță** în tab-ul Acasă. Cât e pornit:
- zilele de vacanță nu intră în învățarea obiceiurilor;
- observațiile mărunte („lăsat prea mult”, „senzor tăcut”, „aprinderi repetate”) tac;
- orice mișcare sau ușă/fereastră deschisă în casă ajunge imediat pe telefon (`vacation.security_alerts`).

**M-am întors** îl oprește; revine la automat imediat ce ajunge cineva acasă. Există și ca
`binary_sensor.vatra_vacation` (MQTT).

## Raport săptămânal

Duminică, la ora rezumatului (`agents.digest_hour`), un singur mesaj: obiceiuri și automatizări noi, acțiuni (și
anulări), alerte, observații, curățenie și zile de vacanță. Același rezumat apare în tab-ul Acasă, la
**Săptămâna asta**. Se oprește cu `weekly_report: false`.

## Curățenie

La câteva ore, Vatra caută dispozitivele ale căror entități sunt **toate** indisponibile acum **și** n-au avut nicio
valoare reală în istoricul Home Assistant în ultimele `cleanup.days` zile (implicit 7) – dispozitive vândute,
containere Docker șterse, integrări abandonate. Fiecare apare în **Aprobări** (fără notificare pe telefon):
**Dezactivează** le oprește entitățile în registrul HA (nu șterge nimic), **Păstrează** înseamnă că nu mai întreabă.
**Anulează** din Jurnal le reactivează.

## Entitățile Vatra (MQTT)

Dacă Home Assistant are **integrarea MQTT** configurată (de exemplu cu aplicația Mosquitto), Vatra publică prin ea –
fără parole – și apare un dispozitiv **Vatra**:

| Entitate | Ce arată |
|---|---|
| `sensor.vatra_active_alerts` | Numărul alertelor active; lista e în atribute |
| `sensor.vatra_pending_approvals` | Cererile care așteaptă răspunsul tău |
| `binary_sensor.vatra_problem` | Pornit când e activă o defecțiune confirmată |
| `sensor.vatra_last_alert` | Titlul celei mai noi alerte |
| `sensor.vatra_unusual` | Observațiile neobișnuite |
| `sensor.vatra_cleanup` | Dispozitivele moarte care pot fi dezactivate |

Exemplu: un bec devine roșu cât timp `binary_sensor.vatra_problem` e pornit. Se oprește cu `mqtt_entities: false`.

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
language: auto
site_context: "Apartament în Cluj. Locuim Razvan și Hajni, lucrăm L–V 8:00–16:30."
notify_services: [notify.mobile_app_telefon]
learning:
  persons: [person.razvan, person.hajni]   # pentru „doar când e cineva acasă”
assistant:
  backend: ollama      # sau: openai
  ollama_url: "http://IP:11434"
  # openai_url: "http://IP:1234/v1"   # LM Studio; llama.cpp: http://IP:8080/v1
  # api_key: ""                       # doar dacă serverul cere
  # Cloud (opțional, cu cheie API): OpenAI https://api.openai.com/v1 · Claude https://api.anthropic.com/v1
  model: "qwen3.5:9b"
  num_ctx: 8192        # Ollama: același ca integrarea Ollama din HA, ca modelul să nu se reîncarce
  # extra_body: '{"chat_template_kwargs": {"enable_thinking": false}}'   # tip OpenAI: modelele care „gândesc” răspund mai repede
agents:
  agents_interval_hours: 6
  quiet_hours: "23-7"  # agenții nu rulează analize zgomotoase noaptea
```

Paznicul (dispozitive indisponibile, baterii) și Jarvis (chat) funcționează ca înainte.

## Securitate

Panoul răspunde doar cererilor venite prin ingress-ul Home Assistant. Datele stau în `/data/brain.db`.
