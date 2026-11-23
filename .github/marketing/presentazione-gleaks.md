# GLeaks: nota di marketing

> Materiale interno per presentare GLeaks: messaggi chiave, pubblico, testi pronti da usare.
> Ogni affermazione qui sotto corrisponde a ciò che l'app fa oggi (versione 0.1). Se il prodotto cambia, aggiorna questa nota prima di riusare i testi.

---

## In una riga

**GLeaks: scopri dove sono finiti i tuoi dati.**

## In tre righe

GLeaks è un'app nativa per GNOME che ricostruisce la tua impronta pubblica: violazioni di dati, pagine profilo e menzioni sul web.
Tutto resta cifrato sul tuo disco e ogni passaggio è registrato.
Niente account, niente cloud, nessuna chiave API obbligatoria.

## Tagline alternative

- Know where your data has leaked. *(quella ufficiale, in inglese)*
- La tua impronta digitale, sul tuo computer e non nel cloud di qualcun altro.
- Controlla la tua esposizione online senza esporti di più.
- Lento di proposito, trasparente per scelta.

---

## Il problema

Nel corso degli anni ognuno di noi lascia in giro decine di identificatori: email, nickname, nome e cognome. Finiscono in database che vengono violati, in pagine profilo dimenticate, in risultati di ricerca che non controlliamo.

Gli strumenti che esistono di solito:

- guardano una sola categoria di rischio (solo i data breach, solo gli username);
- chiedono di creare un account e di consegnare i propri dati a un servizio online;
- restituiscono un "punteggio di rischio" opaco invece dei fatti.

Il paradosso: per sapere quanto sei esposto, devi esporti ancora di più.

## La risposta di GLeaks

Inserisci gli identificatori che sono tuoi. GLeaks li verifica con più fonti indipendenti e conserva ciò che scopre in **un unico file cifrato, sul tuo computer**.

| Fonte | Cosa trova | Serve una chiave? |
|---|---|---|
| **Indice dei profili** | Su quali di 28 siti esiste una pagina con quel nome, per esempio `github.com/tuonome` | No |
| **Ricerca web** | Pagine pubbliche che citano esattamente l'identificatore | No |
| **Have I Been Pwned** | Violazioni di dati note che includono l'indirizzo email | Sì, la tua (a pagamento), facoltativa |

Le fonti lavorano in parallelo: se una fallisce, le altre continuano.

---

## Messaggi chiave

### 1. I tuoi dati restano tuoi
- Nessun account, nessun backend, nessun cloud.
- Il profilo `.gleaks` è cifrato con AES-256-GCM e non tocca mai il disco in chiaro, nemmeno temporaneamente.
- È un solo file: lo porti da un computer all'altro.

### 2. Trasparenza totale
- **Approvi ogni scansione.** Prima che qualcosa esca dal computer, GLeaks mostra cosa verrà inviato e a chi.
- **Ogni passaggio è registrato.** La scheda Attività mostra, fonte per fonte, ogni richiesta inviata e ogni risposta ricevuta.

### 3. Onesto per costruzione
- **Un errore non è mai un "tutto a posto".** Un controllo fallito viene mostrato come fallito; una risposta ambigua come sconosciuta.
- **Fatti, non punteggi.** Niente rating: gli eventi restano nello storico, accanto ad azioni suggerite che puoi tracciare.

### 4. Lento di proposito
- Gli strumenti di GLeaks non inondano il web: una richiesta alla volta, 30 secondi di distanza per impostazione predefinita.
- Le ricerche si mettono in pausa, riprendono e sopravvivono alla chiusura dell'app.
- Possono continuare in background e ripetersi ogni giorno, settimana o mese.
- Se un sito chiede di rallentare, GLeaks lo lascia in pace per ore.

### 5. Nativo GNOME, libero
- GTK 4 e Libadwaita: si integra con il desktop come un'app di sistema.
- Open source con licenza MIT. Aggiungere un sito all'indice richiede una riga in un file JSON, senza codice.

---

## A chi parliamo

| Pubblico | Cosa gli importa | Messaggio da spingere |
|---|---|---|
| **Utenti Linux/GNOME attenti alla privacy** | Software locale, niente telemetria, integrazione col desktop | Nativo GNOME, local-first, nessun account |
| **Sviluppatori e persone con presenza online** | Sapere dove compare il proprio nickname, vecchi account dimenticati | Indice dei profili e ricerca web senza chiavi API |
| **Comunità privacy e self-hosting** | Trasparenza, controllo, nessun dark pattern | Ogni richiesta approvata e registrata, file cifrato portabile |
| **Contributori open source** | Progetto pulito, facile da estendere | Un sito nuovo = una voce in `sites.json`, PR benvenute |

---

## Cosa NON dire

Per restare credibili, evitiamo promesse che il prodotto non mantiene:

- ❌ "Ti dice se sei al sicuro." Un risultato vuoto copre solo ciò che queste fonti vedono; non prova che nulla sia trapelato.
- ❌ "Trova tutti i tuoi account." Siti dietro login (Instagram, X, LinkedIn, Facebook) non sono nell'indice.
- ❌ "Quel profilo è tuo." Una pagina con il tuo nickname può appartenere a qualcun altro: GLeaks segnala che esiste, il giudizio resta all'utente.
- ❌ "Scansione istantanea." Le ricerche proprie sono lente di proposito (un nickname richiede circa un quarto d'ora). Va presentato come un pregio, non nascosto.
- ❌ Qualunque uso per cercare altre persone. GLeaks è pensato per i *propri* identificatori: va detto sempre.
- ❌ "Disponibile su Flathub / negli store." Al momento non c'è ancora un pacchetto rilasciato: si avvia dai sorgenti o dal Flatpak prodotto dalla CI.

---

## Testi pronti

### Post breve (Mastodon / Bluesky)

> Ho rilasciato GLeaks, un'app GNOME per scoprire dove sono finiti i tuoi dati: violazioni, pagine profilo, menzioni sul web.
> Tutto cifrato sul tuo disco, ogni richiesta approvata e registrata. Niente account, niente cloud.
> Open source, MIT. 🔒🐧
> https://github.com/openapi/gleaks
> #GNOME #Linux #Privacy #OpenSource

### Post in inglese (Reddit r/gnome, r/linux, r/privacy)

**Title:** GLeaks – a native GNOME app to see where your personal data has leaked, fully local

> I built GLeaks, a GTK 4 / Libadwaita app that checks your own email, nickname and name against several independent sources: a profile index of 28 sites, web search, and optionally Have I Been Pwned with your own key.
>
> What I cared about:
> - **No account, no cloud.** Everything lives in one AES-256-GCM encrypted file you can move between machines.
> - **You approve every scan** and see exactly what is sent and to whom. Every request and answer is logged.
> - **An error is never "all clear".** Failed checks are reported as failed, unclear answers as unknown.
> - **Slow on purpose.** One request every 30 seconds, resumable, can run in the background.
>
> It's an early 0.1, runs from source on Ubuntu 24.04+ / Debian 13+. Feedback and PRs welcome, especially new sites for the index (one JSON entry, no code).
>
> https://github.com/openapi/gleaks

### Show HN

**Title:** Show HN: GLeaks – local-first personal data exposure monitor for GNOME

> GLeaks reconstructs your public footprint (breaches, profile pages, web mentions) from identifiers you own. It's local-first: no account, no backend, a single encrypted profile file. Every outbound request needs your approval and is logged. It deliberately rate-limits itself to one request every 30 seconds so it never hammers the sites it checks.

### Boilerplate (per articoli e comunicati)

> **GLeaks** è un'applicazione desktop open source per GNOME che aiuta le persone a capire quanto e dove i propri dati personali sono esposti su Internet. Verifica email, nickname e nomi con fonti indipendenti e conserva i risultati in un profilo locale cifrato, senza account né servizi cloud. Ogni trasmissione verso l'esterno è approvata dall'utente e registrata. GLeaks è rilasciato con licenza MIT.

---

## Materiali disponibili

- **Icona dell'app:** `data/icons/hicolor/scalable/apps/io.github.openapi.GLeaks.svg`
- **Anteprima animata:** `docs/gleaks-demo.svg` (motore reale con risposte simulate e identificatori fittizi; si rigenera con `make demo-svg`)
- **Visione di prodotto:** `IDEA.md`
- **Modello delle minacce:** `SECURITY.md`

Per screenshot e video usa sempre identificatori fittizi, mai dati reali.

## Prossimi passi suggeriti

1. Pubblicare un pacchetto (Flathub o `.deb`) prima del lancio pubblico: senza, la conversione da post a utente è bassa.
2. Preparare 3-4 screenshot statici (scheda Attività, conferma prima della scansione, risultati).
3. Lanciare prima nelle comunità GNOME e privacy, poi Show HN.
4. Aprire alcune issue "good first issue" sull'aggiunta di siti all'indice per accogliere i nuovi contributori.

---

## Credits da citare

I dati sulle violazioni sono forniti da [Have I Been Pwned](https://haveibeenpwned.com). I risultati web vengono da [Marginalia Search](https://marginalia-search.com) e [DuckDuckGo](https://duckduckgo.com). GLeaks è indipendente e non è affiliato a nessuno di loro, né a GNOME o Ubuntu.
