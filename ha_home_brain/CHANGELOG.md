# Changelog

## 2.7.2 – Fixes from issues #3 and #5
- EN: OpenAI-compatible servers that answer 502/500 when the model writes prose instead of JSON (Strata, vLLM with guided decoding) are retried once without `response_format`, so Jarvis answers instead of "can't reach the AI model". Thanks @anilv26 (#3)
- EN: New option `assistant.extra_body`: extra JSON fields for every request, e.g. `{"chat_template_kwargs": {"enable_thinking": false}}` so a thinking model answers about 10 s faster
- EN: Jarvis sends the changing house state with the question, after the fixed system prompt and the history, so servers can reuse their prompt cache
- EN: Code review fixes, thanks @bek00letz (#5): a dead sensor no longer clears its own "silent" alert after a day and a half; "Seen" now removes a finding from the panel and the evening digest for 24 h; a failed database write is rolled back instead of blocking every later write, and the data is kept; important devices are also recognised by their friendly name (a fridge on `switch.plug_01`), and `cover.toggle` / `cover.set_cover_position` need approval like `open_cover`; changes with both a person and a parent context count as the person's; radiator valves get a value they can hold (no command loop with 0.5 °C steps); the boiler comes back after an AC heated even if Vatra restarted in between; the panel escapes single quotes; the Assist code is compared in constant time; Hungarian for the Assist integration
- RO: Serverele compatibile OpenAI care răspund 502/500 când modelul scrie text în loc de JSON (Strata, vLLM cu guided decoding) primesc o a doua încercare fără `response_format`, așa că Jarvis răspunde în loc de „nu pot ajunge la modelul AI”. Mulțumiri @anilv26 (#3)
- RO: Opțiune nouă `assistant.extra_body`: câmpuri JSON în plus la fiecare cerere, ex. `{"chat_template_kwargs": {"enable_thinking": false}}` ca un model care „gândește” să răspundă cu ~10 s mai repede
- RO: Jarvis trimite starea casei (care se schimbă) împreună cu întrebarea, după promptul fix și istoric, ca serverul să-și poată refolosi cache-ul
- RO: Corecturi din code review, mulțumiri @bek00letz (#5): un senzor mort nu-și mai șterge singur alerta „tace” după o zi și jumătate; „Văzut” scoate constatarea din panou și din rezumatul de seară pentru 24 h; o scriere eșuată în baza de date e anulată în loc să blocheze toate scrierile următoare, iar datele se păstrează; dispozitivele importante sunt recunoscute și după nume (un frigider pe `switch.plug_01`), iar `cover.toggle` / `cover.set_cover_position` cer aprobare ca `open_cover`; schimbările cu persoană și context-părinte contează ca ale persoanei; robinetele termostatate primesc o valoare pe care o pot ține (fără bucla de comenzi la pași de 0,5 °C); centrala revine după ce a încălzit AC-ul chiar dacă Vatra a repornit între timp; panoul escapează apostroful; codul Assist e comparat în timp constant; maghiară pentru integrarea Assist

## 2.7.1 – Magyar
- EN: Hungarian translation – notifications, AI prompts, panel and settings form. Thanks to @Zsoltey!
- RO: Traducere în maghiară – notificări, prompturi AI, panou și formularul de setări. Mulțumiri lui @Zsoltey!

## 2.7.0 – One file per language
- EN: All texts of a language now live in one file, `app/locales/<code>.json` (notifications, prompts and the web panel), with English as fallback for anything not translated. A new language is picked up automatically; the panel has a language list that shows how complete each translation is. Hungarian (`hu`) is added to the `language` option, ready for the community translation. Guide: TRANSLATING.md.
- RO: Toate textele unei limbi stau acum într-un singur fișier, `app/locales/<cod>.json` (notificări, prompturi și panoul web), cu engleza drept rezervă pentru ce nu e tradus. O limbă nouă e preluată automat; panoul are o listă de limbi care arată cât de completă e fiecare traducere. Maghiara (`hu`) e adăugată în opțiunea `language`, pregătită pentru traducerea din comunitate. Ghid: TRANSLATING.md.

## 2.6.3 – Better Jarvis by voice
- EN: Jarvis now knows Vatra's own state – active alerts grouped per device, pending approvals, dead devices to clean up, vacation mode – so "how many alerts are there?" gets the real answer. Voice answers (Assist) are short plain sentences with friendly names, without Markdown.
- RO: Jarvis știe acum și starea Vatra – alertele active grupate pe dispozitiv, aprobările în așteptare, dispozitivele moarte de curățat, modul vacanță – așa că la „câte alerte sunt?” primești răspunsul real. Răspunsurile vocale (Assist) sunt propoziții scurte, cu nume prietenoase, fără Markdown.

## 2.6.2
- EN: OpenAI-compatible servers that only accept the default temperature (Claude 4.7+ through `https://api.anthropic.com/v1`, OpenAI reasoning models) now work: on a 400, Vatra retries without the optional fields and remembers. Docs show the cloud addresses for OpenAI and Claude.
- RO: Serverele compatibile OpenAI care acceptă doar temperatura implicită (Claude 4.7+ prin `https://api.anthropic.com/v1`, modelele de raționament OpenAI) merg acum: la o eroare 400, Vatra reîncearcă fără câmpurile opționale și ține minte. Documentația arată adresele cloud pentru OpenAI și Claude.

## 2.6.1
- EN: MQTT publishes are no longer written to the log every minute (debug level only).
- RO: Publicările MQTT nu mai sunt scrise în log la fiecare minut (doar la nivel debug).

## 2.6.0 – Jarvis by voice (Assist)
**EN:**
- **Jarvis in Assist:** a small companion integration (HACS → custom repository, category Integration) adds
  *Vatra Jarvis* as a conversation agent – talk to it from the phone app, a watch or a voice satellite. Vatra
  announces itself, so Home Assistant discovers it with one click; a secret code protects the connection.
- Panel → Setup → **Voice (Assist)** with the steps and the manual address/code.
- Weekly report: alert counts now survive restarts ("N new and M fixed this week").

**RO:**
- **Jarvis în Assist:** o mică integrare însoțitoare (HACS → custom repository, categoria Integration) adaugă
  *Vatra Jarvis* ca agent de conversație – îi vorbești din aplicația de telefon, de pe ceas sau de pe un satelit
  vocal. Vatra se anunță singur, așa că Home Assistant îl descoperă cu un click; un cod secret protejează legătura.
- Panou → Configurare → **Voce (Assist)**, cu pașii și adresa/codul pentru varianta manuală.
- Raport săptămânal: numărul de alerte nu se mai pierde la repornire („N noi și M rezolvate săptămâna asta”).

## 2.5.0 – Vacation mode and weekly report
**EN:**
- **Vacation mode:** turns on by itself when everyone has been away for 24 h (or from the Home tab). Vacation days
  are left out of habit learning, small observations go quiet, and motion or doors opening in the empty house are
  sent to your phone right away. "I'm back" turns it off. Options under `vacation`; `binary_sensor.vatra_vacation`.
- **Weekly report:** Sunday evening, one message with what Vatra learned, did and noticed this week; also on the
  Home tab ("This week"), with a button to send it now. Option `weekly_report`.

**RO:**
- **Mod vacanță:** pornește singur când toată lumea e plecată de 24 de ore (sau din tab-ul Acasă). Zilele de vacanță
  nu intră în învățarea obiceiurilor, observațiile mărunte tac, iar mișcarea sau ușile deschise în casa goală ajung
  imediat pe telefon. „M-am întors” îl oprește. Opțiuni la `vacation`; `binary_sensor.vatra_vacation`.
- **Raport săptămânal:** duminică seara, un mesaj cu ce a învățat, ce a făcut și ce a observat Vatra în săptămâna
  respectivă; apare și în tab-ul Acasă („Săptămâna asta”), cu buton de trimitere imediată. Opțiune `weekly_report`.

## 2.4.3 – Safer clean up
- EN: Clean up no longer treats "unknown" as dead (notify, button, scene and some select entities sit on "unknown"
  normally), skips TVs/media players and phones that are simply off or away, and never proposes an entity with no
  history. Proposals made by 2.4.0–2.4.2 that no longer qualify are withdrawn automatically.
- RO: Curățenia nu mai consideră „unknown” ca mort (entitățile notify, buton, scenă și unele select stau normal pe
  „unknown”), sare peste televizoare/media playere și telefoane care sunt doar oprite sau plecate și nu mai propune
  entități fără istoric. Propunerile făcute de 2.4.0–2.4.2 care nu mai corespund se retrag automat.

## 2.4.2
- EN: Vatra entities are now published through Home Assistant's own MQTT integration (`mqtt.publish`): works with any broker HA uses, no Supervisor service or passwords needed. Entities become unavailable within 5 minutes if Vatra stops.
- RO: Entitățile Vatra se publică acum prin integrarea MQTT a Home Assistant (`mqtt.publish`): merge cu orice broker folosește HA, fără serviciu Supervisor sau parole. Dacă Vatra se oprește, entitățile devin indisponibile în cel mult 5 minute.

## 2.4.1
- EN: MQTT: the reason is now shown in the log and in the panel status when the Vatra entities can't be published; faster first retry.
- RO: MQTT: motivul apare acum în log și în starea panoului când entitățile Vatra nu pot fi publicate; prima reîncercare e mai rapidă.

## 2.4.0 – Clean up and Vatra entities
**EN:**
- **Clean up:** Vatra finds devices that have had no value for over a week (checked against Home Assistant's
  history) – sold devices, deleted containers, abandoned integrations – and offers to disable their entities, in the
  Approvals tab. Nothing is deleted; Undo in the Log enables them again. Options: `cleanup.enabled`, `cleanup.days`.
- **Vatra entities via MQTT:** if you have an MQTT broker (e.g. Mosquitto), a *Vatra* device appears with
  active alerts, pending approvals, problem, last alert, unusual observations and dead devices – for dashboards
  and automations. Option: `mqtt_entities`.
- The evening digest mentions dead devices that can be cleaned up.

**RO:**
- **Curățenie:** Vatra găsește dispozitivele care n-au mai avut nicio valoare de peste o săptămână (verificat în
  istoricul Home Assistant) – dispozitive vândute, containere șterse, integrări abandonate – și propune să le
  dezactiveze entitățile, în tab-ul Aprobări. Nu șterge nimic; Anulează din Jurnal le reactivează.
  Opțiuni: `cleanup.enabled`, `cleanup.days`.
- **Entitățile Vatra prin MQTT:** dacă ai un broker MQTT (ex. Mosquitto), apare un dispozitiv *Vatra* cu alerte
  active, aprobări în așteptare, problemă, ultima alertă, observații neobișnuite și dispozitive moarte – pentru
  dashboard-uri și automatizări. Opțiune: `mqtt_entities`.
- Rezumatul de seară amintește dispozitivele moarte care pot fi curățate.

## 2.3.0 – Alerts grouped by device
**EN:**
- When several entities of the same device (or integration) go down together, the phone gets **one** message:
  "Dishwasher Bosch is not responding – 4 entities unavailable: Connected, Remote Start…" instead of a long list.
- In the panel, alerts of the same device are one row that opens to show each entity, with a link to its history.
- Summary messages now count entities, not "devices".
- Issue templates on GitHub (bug, idea, new language), in English and Romanian.

**RO:**
- Când mai multe entități ale aceluiași dispozitiv (sau aceleiași integrări) pică deodată, pe telefon vine **un singur**
  mesaj: „Dishwasher Bosch nu răspunde – 4 entități indisponibile: Connected, Remote Start…”, în loc de o listă lungă.
- În panou, alertele aceluiași dispozitiv sunt un singur rând, care se deschide și arată fiecare entitate, cu link
  spre istoricul ei.
- Mesajele rezumat numără acum entități, nu „dispozitive”.
- Template-uri de issue pe GitHub (problemă, idee, limbă nouă), în engleză și română.

## 2.2.1 – Alert details fix
**EN:**
- Guard alerts (low battery, device unavailable) that were active before a restart showed no details. They now
  show the device name, the battery level or state, and the entity, with a link to its history in Home Assistant.
- Entities you add to `guard.ignore` later now also close their alerts that were already active.

**RO:**
- Alertele paznicului (baterie slabă, dispozitiv indisponibil) active dinainte de o repornire apăreau fără detalii.
  Acum arată numele dispozitivului, nivelul bateriei sau starea și entitatea, cu link spre istoricul ei din Home Assistant.
- Entitățile adăugate ulterior la `guard.ignore` își închid și alertele deja active.

## 2.2.0 – Setup guide, any local AI server, ready-made images
**EN:**
- **Setup guide in the panel (⚙ Setup)** – no YAML needed. It finds your phones (`notify.mobile_app_*`) and
  people (`person.*`), lets you send a test notification, **searches your network for an AI server**
  (Ollama on port 11434, LM Studio 1234 / llama.cpp 8080 on the HA machine), fills in the model list, then saves
  the options and restarts Vatra. Opens by itself the first time. Advanced options stay in the Configuration tab.
- **OpenAI-compatible AI servers**: new `assistant.backend` (`ollama` / `openai`), `openai_url` and `api_key`.
  Works with LM Studio, llama.cpp, vLLM, LocalAI, Jan… Ollama stays the default; nothing changes for existing setups.
- More tolerant reading of the model's JSON (thinking tags, ```json blocks, text around it).
- **Ready-made images** for amd64 and aarch64 are built on GitHub and published on ghcr.io – installs and
  updates no longer build on your machine (slow on a Raspberry Pi).
- Screenshots in the README; the panel header fits on phones.

**RO:**
- **Ghid de pornire în panou (⚙ Configurare)** – fără YAML. Găsește telefoanele (`notify.mobile_app_*`) și
  persoanele (`person.*`), trimite o notificare de test, **caută serverul AI în rețea** (Ollama pe portul 11434,
  LM Studio 1234 / llama.cpp 8080 pe mașina HA), completează lista de modele, apoi salvează opțiunile și
  repornește Vatra. Se deschide singur prima dată. Opțiunile avansate rămân în tab-ul Configuration.
- **Servere AI compatibile OpenAI**: opțiuni noi `assistant.backend` (`ollama` / `openai`), `openai_url` și
  `api_key`. Merge cu LM Studio, llama.cpp, vLLM, LocalAI, Jan… Ollama rămâne implicit; la cine are deja
  Vatra configurat nu se schimbă nimic.
- Citire mai tolerantă a JSON-ului de la model (taguri de gândire, blocuri ```json, text în jur).
- **Imagini gata construite** pentru amd64 și aarch64, făcute pe GitHub și publicate pe ghcr.io – instalarea
  și update-urile nu mai construiesc nimic pe mașina ta (lent pe un Raspberry Pi).
- Capturi de ecran în README; antetul panoului încape pe telefon.

## 2.1.0 – English 🇬🇧 / Română 🇷🇴
**EN:** Vatra now speaks English and Romanian.
- New option `language`: `auto` (default) follows the Home Assistant language – Romanian if HA is in
  Romanian, English otherwise; or force `en` / `ro`.
- Notifications, evening digest, approval buttons, guard messages, habit descriptions and the AI agents'
  instructions are translated. Jarvis answers in the language you write to it.
- The panel starts in the add-on language and has an **EN/RO** switch, remembered per browser/phone.
- Configuration screen translated (HA shows it in your language).
- Add-on documentation is now in English; Romanian moved to `DOCS.ro.md`.
- Add-on logs are in English. The personal "RusHome" name was removed from the AI prompts.

**RO:** Vatra vorbește acum engleză și română.
- Opțiune nouă `language`: `auto` (implicit) urmează limba Home Assistant – română dacă HA e în română,
  altfel engleză; sau forțezi `en` / `ro`.
- Notificările, rezumatul de seară, butoanele de aprobare, mesajele paznicului, descrierile obiceiurilor
  și instrucțiunile agenților AI sunt traduse. Jarvis răspunde în limba în care îi scrii.
- Panoul pornește în limba add-on-ului și are comutator **EN/RO**, ținut minte pe fiecare browser/telefon.
- Ecranul de configurare e tradus (HA îl arată în limba ta).
- Documentația add-on-ului e acum în engleză; cea în română e în `DOCS.ro.md`.
- Logurile add-on-ului sunt în engleză. Numele personal „RusHome” a fost scos din instrucțiunile AI.

## 2.0.0 – V2: context înainte de alarmă, notificări mai puține
Construită din feedback-ul de pe casa reală.

**Notificări mai puține și mai blânde**
- Secțiune nouă `notifications`. Implicit (`smart`): doar alertele critice pleacă imediat; restul se
  strâng și pleacă într-un singur mesaj grupat cel mult o dată la 2 ore, maximum 4 pe zi.
- Ore de liniște (`quiet_hours`, implicit 22–7): noaptea pleacă doar ce e critic; cererile de aprobare
  așteaptă dimineața.
- Mesajele „Rezolvat” rămân doar în panou (`send_resolved: false`).
- O problemă care s-a rezolvat și a revenit nu se mai retrimite timp de 12 ore (`cooldown_hours`).
- Pe Android/iOS: canal propriu „Vatra”, prioritate mică pentru mesajele obișnuite, iar mesajele despre
  același lucru se înlocuiesc în loc să se adune.
- Observațiile „neobișnuite” și bateriile slabe (peste 5%) nu mai ajung pe telefon: le găsești în panou
  și în rezumatul de seară.

**Trei trepte: neobișnuit → posibilă anomalie → defecțiune confirmată**
- Paznicul citește registrul de dispozitive din HA. Un singur senzor fără valoare, cât timp restul
  dispozitivului funcționează, e „posibilă anomalie” (doar în panou). Doar când tot dispozitivul a picat
  e „defecțiune confirmată” și ajunge pe telefon.
- Entitățile care pică des și își revin singure (învățat din ultimele 30 de zile) nu mai dau alarmă.

**Fără false anomalii la „unavailable”**
- Dispozitivele în repaus nu mai sunt tratate ca defecte: tracker acasă, la încărcat sau nemișcat
  (ex. GPS-ul trotinetei), robot aspirator în bază (ex. `sensor.d30_ultra_mapping_time` când nu
  cartografiază), senzori care au valoare doar în timpul unei activități (progres, timp rămas, ciclu...).
- Senzorii „tăcuți” se verifică și ei în context: un GPS care stă acasă nu are ce raporta.
- Agenții nu mai pot propune `homeassistant.update_entity`, reload sau reporniri (blocate și în reguli).
- Tab-ul *Neobișnuit* arată și lista „Indisponibil, dar normal”, cu motivul.

**Context energetic**
- Un consum mare nu mai e semnalat cât timp funcționează un consumator mare (pompă de căldură, centrală,
  AC, boiler...), decât dacă depășește clar tot ce s-a văzut vreodată.
- Releele/prizele care țin becurile Zigbee alimentate permanent nu mai sunt confundate cu lumina aprinsă.
- Agenții Energie și Climă primesc lista „Funcționează acum” și stările celorlalte entități ale
  aceluiași dispozitiv, cu reguli explicite pentru cele trei trepte.

**Aprobări din notificare**
- Atingerea notificării deschide panoul Vatra (calea corectă a add-on-ului, aflată de la Supervisor),
  nu o pagină 404. Când există cereri în așteptare, panoul se deschide direct pe *Aprobări*.

## 0.5.1
- Repo-ul s-a mutat la github.com/RazvanR1/Vatra (linkul vechi redirecționează).

## 0.5.0 – Vatra
- Proiectul se numește acum **Vatra – the local brain for Home Assistant** (nume, panou, notificări, documentație). Identificatorul intern și datele rămân aceleași: update-ul nu cere reinstalare și nu pierde nimic.

## 0.4.4
- README public (engleză + română), licență MIT, teste automate pe GitHub, explicații în tab-ul Configuration.

## 0.4.3
- Memoria urmărește și senzorii binari de tip încălzire / putere / funcționare (ex. „centrala funcționează”).

## 0.4.2 – mai puțin zgomot
- Senzori tăcuți: doar cei care se schimbă practic în fiecare oră (nu bateriile, nu ce raportează doar la schimbare).
- Mai mult de 3 lucruri neobișnuite deodată -> o singură notificare rezumat; cel mult 5 pe zi.
- Agenți: fără entități indisponibile și fără automatizări în context, reguli stricte anti-inventat,
  implicit fără acțiuni propuse și fără notificări imediate – un singur rezumat seara (`digest_hour`).
- Curăță observațiile și cererile greșite din 0.4.0/0.4.1.

## 0.4.1
- Paznic: ține minte singur când a văzut ultima oară fiecare dispozitiv funcționând (o repornire HA nu mai face ca tot ce era deja picat să pară nou); alertele deschise rămân salvate peste restarturi, fără notificări duplicate.

## 0.4.0 – creierul
- Memorie locală (SQLite) cu originea fiecărei schimbări; import de istoric la pornire.
- Obiceiuri de oră și de secvență, doar din acțiunile omului, testate pe istoric, filtrate față de
  automatizările existente; automatizări native create la aprobare, cu Undo.
- Detector de neobișnuit: valori anormale pe oră, senzori tăcuți, flapping, stare prea lungă,
  casă deschisă când nu e nimeni; învață din reacții.
- Aprobări din notificare (Aprobă / Mereu / Respinge / Anulează), moduri Shadow / Co-pilot / Autonom,
  guardrails care nu pot fi ocolite.
- Agenți AI locali: Climă, Energie, Securitate, Server & homelab; rulează doar când s-a schimbat ceva.
- Panou nou cu tab-uri; Jarvis știe și ce a observat creierul.

## 0.3.1
- Jarvis: context doar cu entitățile relevante, încadrat în `num_ctx` (implicit 8192, ca integrarea Ollama din HA), răspuns brut afișat dacă modelul nu respectă formatul.

## 0.3.0
- Paznic adaptat la o casă reală: doar `unavailable` (nu `unknown`), sare peste ce e picat de peste 24h,
  nu urmărește media_player (TV-urile stinse), rezumat când pică mai multe deodată,
  alertele se închid doar când problema chiar dispare.
- Jarvis: `think: false` și modelul ținut încărcat (`keep_alive`).

## 0.2.0
- Paznic: dispozitive indisponibile și baterii slabe, cu alertă la rezolvare.
- Automatizări: camere după prezență, centrală blocată când încălzește AC-ul, robinete care urmează termostatul.
- Jarvis: asistent prin Ollama, cu listă de domenii permise.
- Panou web în sidebar (ingress).

## 0.1.0
- Schelet add-on.
