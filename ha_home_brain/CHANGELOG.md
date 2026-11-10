# Changelog

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
