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

## La storia da raccontare

La presentazione di GLeaks non parte dal prodotto. Parte da una storia in tre atti: una persona che ha reso visibili le violazioni di dati, un mondo in cui l'intelligenza artificiale rende quei dati più pericolosi, e il nostro piccolo contributo.

> ⚠️ Prima di pubblicare, verifica date e numeri sul sito di Have I Been Pwned e sul blog di Troy Hunt: i contatori crescono di continuo e una cifra sbagliata toglie credibilità a tutto il resto.

### Atto 1: Have I Been Pwned, l'idea di una persona

Nell'ottobre 2013 Adobe subisce una delle violazioni più grandi dell'epoca: circa 153 milioni di account, con email e password protette male. Troy Hunt, ricercatore di sicurezza australiano, si accorge di una cosa semplice: le persone non hanno modo di sapere se i loro dati sono finiti in quei file.

A dicembre 2013 mette online **Have I Been Pwned**: scrivi la tua email, e il sito ti dice in quali violazioni note compare. Nessuna registrazione, nessuna vendita di paure, solo un fatto.

Da progetto personale diventa un pezzo dell'infrastruttura di Internet:

- negli anni raccoglie **miliardi di account** provenienti da centinaia di violazioni (cita il contatore aggiornato in homepage);
- con **Pwned Passwords** permette di controllare se una password è già trapelata senza inviarla davvero, grazie a una tecnica chiamata *k-anonymity*: al servizio arrivano solo i primi caratteri dell'hash;
- governi, forze dell'ordine e grandi aziende lo usano per avvisare cittadini e utenti; parte del codice è stata resa open source.

Il messaggio da far passare: **una sola persona, con un'idea onesta, ha cambiato il modo in cui milioni di persone scoprono di essere esposte.** È la tradizione in cui GLeaks vuole stare.

### Atto 2: con l'intelligenza artificiale, i dati esposti valgono di più

Per anni un dato trapelato era un rischio, ma sfruttarlo costava fatica: qualcuno doveva incrociare i dati a mano, scrivere un'email credibile, provare le password una per una.

L'intelligenza artificiale abbatte quel costo:

- **Phishing su misura, a scala industriale.** Con nome, email, vecchio nickname e un paio di profili pubblici, un modello linguistico scrive in pochi secondi un messaggio personalizzato, senza errori, nella tua lingua. Prima andava fatto a mano, una vittima alla volta.
- **Profilazione automatica.** Raccogliere e collegare tutte le tracce pubbliche di una persona (profili, menzioni, violazioni) era lavoro da investigatore; oggi lo automatizza un agente in pochi minuti.
- **Impersonificazione.** Voce, stile di scrittura e dettagli personali rendono credibili truffe del tipo "sono io, mi serve un favore".
- **Riuso delle credenziali.** Gli attacchi che provano password trapelate su altri servizi sono automatizzati da tempo, e diventano più efficaci quando il bersaglio è profilato bene.

Il punto non è spaventare: è che **ogni frammento della tua impronta pubblica oggi è materia prima per un attacco più convincente.** Sapere cosa c'è in giro è il primo passo per ridurlo: cambiare una password riusata, chiudere un account dimenticato, sapere che una certa email riceverà phishing mirato.

### Atto 3: il nostro piccolo contributo

GLeaks non pretende di risolvere il problema. È un contributo piccolo e concreto:

- **Mette insieme le fonti.** Have I Been Pwned per le violazioni, più strumenti propri per le pagine profilo e le menzioni sul web: la stessa vista d'insieme che avrebbe un attaccante, ma nelle tue mani.
- **Non diventa un altro punto di raccolta.** Paradossalmente, molti servizi che ti "proteggono" chiedono di consegnare i tuoi dati a un loro server. GLeaks tiene tutto in un file cifrato sul tuo computer, senza account e senza cloud.
- **Si comporta bene con il web.** Una richiesta ogni 30 secondi: l'opposto della raccolta massiva automatizzata che rende possibili gli abusi.
- **È onesto.** Non usa l'intelligenza artificiale per inventare punteggi: mostra fatti, fonti e richieste inviate, e non spaccia mai un errore per un "tutto a posto".
- **È libero.** Open source, MIT: chiunque può verificare cosa fa, migliorarlo, aggiungere un sito.

La frase che chiude la storia: **se l'intelligenza artificiale rende più facile usare la tua impronta contro di te, il minimo è che tu possa vederla per primo.**

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
- ❌ Allarmismo sull'intelligenza artificiale. Il tono è "sapere per decidere", non "sei in pericolo, scarica subito". Niente cifre sugli attacchi senza una fonte citata.
- ❌ "GLeaks ti protegge dagli attacchi con l'IA." Ti fa vedere cosa è esposto; la protezione viene dalle azioni che prendi dopo.
- ❌ Lasciar intendere un legame con Have I Been Pwned o Troy Hunt. Raccontiamo la loro storia con rispetto e li citiamo, ma GLeaks è indipendente e usa la loro API con la chiave dell'utente.
- ❌ Qualunque uso per cercare altre persone. GLeaks è pensato per i *propri* identificatori: va detto sempre.
- ❌ "Disponibile su Flathub / negli store." Al momento non c'è ancora un pacchetto rilasciato: si avvia dai sorgenti o dal Flatpak prodotto dalla CI.

---

## Testi pronti

### Articolo per blog o newsletter (bozza)

**Titolo:** Tredici anni dopo Have I Been Pwned, l'IA ha cambiato le regole. Ecco il nostro piccolo contributo.

> Nel 2013, dopo la violazione di Adobe, un ricercatore australiano di nome Troy Hunt si pose una domanda semplice: come fa una persona normale a sapere se i suoi dati sono finiti in giro? La risposta fu Have I Been Pwned, un sito dove scrivi la tua email e scopri in quali violazioni compare. Nessun account, nessuna paura venduta a caro prezzo: solo un fatto. Da allora è diventato uno strumento usato da milioni di persone, aziende e governi.
>
> Oggi il contesto è cambiato. Un dato trapelato non resta più fermo in un file: l'intelligenza artificiale permette di incrociarlo con profili pubblici e menzioni sul web e di trasformarlo, in pochi secondi, in un'email di phishing scritta su misura per te. Quello che prima richiedeva ore di lavoro per una sola vittima, ora si fa per migliaia.
>
> Non possiamo cancellare quello che è già in giro. Possiamo però vederlo prima di chi vuole usarlo. Per questo, come Openapi, abbiamo creato GLeaks, un'app open source per il desktop GNOME che mette insieme Have I Been Pwned, un indice di 28 siti di profili e la ricerca web, e ti mostra la tua impronta pubblica. Tutto resta in un file cifrato sul tuo computer: niente account, niente cloud. Ogni richiesta la approvi tu e la vedi registrata.
>
> È un contributo piccolo, e vogliamo che resti onesto: un risultato vuoto non significa che sei al sicuro, e una pagina col tuo nickname potrebbe essere di qualcun altro. Ma sapere cosa c'è in giro è il primo passo per chiudere un account dimenticato, cambiare una password riusata, o riconoscere un messaggio troppo ben fatto per essere vero.
>
> GLeaks è gratuito e con licenza MIT: https://github.com/openapi/gleaks

### Thread (Mastodon / Bluesky)

> 1/ Nel 2013 Troy Hunt creò Have I Been Pwned per una ragione semplice: tutti dovrebbero poter sapere se i propri dati sono finiti in una violazione. 🧵
>
> 2/ Oggi quei dati valgono di più. Con l'IA, nome + email + un vecchio nickname bastano per un phishing su misura, scritto in pochi secondi e senza errori.
>
> 3/ Non possiamo cancellare ciò che è trapelato. Possiamo vederlo prima degli altri.
>
> 4/ Come Openapi abbiamo creato GLeaks, il nostro piccolo contributo: app GNOME open source che unisce HIBP, 28 siti di profili e ricerca web. File cifrato sul tuo disco, niente account, ogni richiesta approvata da te.
> https://github.com/openapi/gleaks #Privacy #GNOME #Linux

### Post breve (Mastodon / Bluesky)

> Come Openapi abbiamo creato GLeaks, un'app GNOME per scoprire dove sono finiti i tuoi dati: violazioni, pagine profilo, menzioni sul web.
> Tutto cifrato sul tuo disco, ogni richiesta approvata e registrata. Niente account, niente cloud.
> Open source, MIT. 🔒🐧
> https://github.com/openapi/gleaks
> #GNOME #Linux #Privacy #OpenSource

### Post in inglese (Reddit r/gnome, r/linux, r/privacy)

**Title:** GLeaks – a native GNOME app to see where your personal data has leaked, fully local

> At Openapi we built GLeaks, a GTK 4 / Libadwaita app that checks your own email, nickname and name against several independent sources: a profile index of 28 sites, web search, and optionally Have I Been Pwned with your own key.
>
> What we cared about:
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
