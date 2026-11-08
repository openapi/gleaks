# GLeaks
## Personal Data Exposure Monitor for GNOME

**Tipo:** Applicazione desktop open source  
**Piattaforma principale:** GNOME / Linux / Ubuntu  
**Architettura:** Local-first, profile-based, extensible  
**Licenza proposta:** GPL-3.0-or-later  
**Stato:** Concept / Pre-development  
**Versione del documento:** 0.1 — 8 novembre 2026

---

## 1. Executive Summary

**GLeaks è un'applicazione desktop nativa GNOME che permette agli utenti di analizzare, monitorare e comprendere l'esposizione dei propri dati personali su Internet.**

L'applicazione consente di creare un profilo locale contenente le proprie identità digitali, come indirizzi email, username, domini e altri identificatori.

Attraverso un sistema modulare di connettori, GLeaks interroga servizi esterni specializzati nell'individuazione di violazioni dei dati, credenziali compromesse e informazioni personali esposte.

I risultati vengono raccolti, normalizzati e conservati in un database SQLite associato al profilo dell'utente.

L'obiettivo non è costruire un semplice motore di ricerca per fughe di dati, ma un ambiente personale di osservazione e gestione dell'esposizione digitale.

**Principio fondamentale: i dati appartengono all'utente, non all'applicazione o a un servizio cloud.**

GLeaks non deve richiedere un account centralizzato, non deve dipendere da un backend proprietario e deve rendere trasparente qualsiasi trasmissione di informazioni personali verso servizi esterni.

### Visione

> Rendere visibile, comprensibile e gestibile l'esposizione dei propri dati personali su Internet attraverso un'applicazione libera, trasparente e integrata nell'esperienza desktop GNOME.

### Posizionamento

GLeaks si colloca tra:

- I servizi di data breach monitoring.
- Gli strumenti di personal privacy management.
- I software di digital identity inventory.
- Gli strumenti di analisi dell'impronta digitale.
- Le applicazioni desktop local-first.

La sua differenziazione principale è l'unione tra monitoraggio delle esposizioni, archivio personale portabile, tracciabilità storica e gestione delle azioni correttive.

---

## 2. Il problema

Nel corso della propria vita digitale una persona utilizza numerosi identificatori:

- Indirizzi email personali e professionali.
- Username e nickname.
- Numeri telefonici.
- Nomi di dominio.
- Account presso servizi online.
- Altri identificatori personali.

Queste informazioni vengono distribuite tra centinaia di servizi.

Nel tempo possono verificarsi:

1. Violazioni dei database dei fornitori.
2. Esposizioni accidentali di informazioni.
3. Diffusione di credenziali.
4. Pubblicazione di dataset contenenti dati personali.
5. Aggregazione e correlazione delle identità.
6. Comparsa di informazioni personali nei risultati di ricerca.
7. Furto di credenziali mediante malware.

L'utente dispone raramente di una visione centralizzata di questi eventi.

Gli strumenti disponibili tendono a concentrarsi su una singola categoria di rischio oppure richiedono l'utilizzo di piattaforme online.

GLeaks propone un modello differente: un archivio personale che conserva nel tempo ciò che è stato scoperto e permette di comprendere come evolve la propria esposizione digitale.

---

## 3. Identità del prodotto

### Nome

**GLeaks**

Il nome combina il richiamo storico alle applicazioni GNOME con il termine inglese *leaks*, ossia fughe o divulgazioni di informazioni.

È un nome breve, facile da pronunciare e adatto all'identificazione di un progetto open source.

### Tagline

**Know where your data has leaked.**

### Descrizione breve

GLeaks helps you discover, understand, and manage personal data exposures from your GNOME desktop.

### Descrizione italiana

GLeaks permette di individuare e monitorare le esposizioni dei propri dati personali direttamente dal desktop, mantenendo il controllo delle informazioni raccolte.

### Naming tecnico proposto

- Nome applicazione: `GLeaks`
- Eseguibile: `gleaks`
- Nome repository: `gleaks`
- Estensione del profilo: `.gleaks`
- Application ID provvisorio: `io.github.ORGANIZATION.GLeaks`

L'Application ID definitivo dovrà utilizzare uno spazio dei nomi effettivamente controllato dal progetto.

### Coerenza GNOME

Il nome richiama la tradizione storica di progetti come gedit e gThumb.

Va tuttavia riconosciuto che le attuali linee guida GNOME sconsigliano i nomi con prefisso G. La scelta di GLeaks rappresenta quindi una decisione intenzionale di branding, non una conformità completa alle convenzioni moderne.

Il progetto non dovrà presentarsi come prodotto ufficiale GNOME o Ubuntu senza un relativo riconoscimento.

---

## 4. Principi di progettazione

### 4.1 Local-first

Ogni profilo risiede sul dispositivo dell'utente.

Le informazioni personali e i risultati delle analisi devono essere conservati localmente.

Non è previsto un database centrale di GLeaks.

### 4.2 Privacy by design

Ogni connettore deve dichiarare:

- Quali dati riceve.
- Quali informazioni trasmette.
- A quale servizio le trasmette.
- Se richiede autenticazione.
- Quali costi o limitazioni applica.
- Quali informazioni restituisce.

Il consenso dell'utente deve precedere le interrogazioni che comportano la trasmissione di identificatori personali.

### 4.3 Trasparenza

I risultati devono indicare esplicitamente origine, data della verifica, attendibilità e limitazioni della fonte.

GLeaks non deve presentare ipotesi o correlazioni come fatti verificati.

### 4.4 Controllo dell'utente

L'utente può creare, aprire, esportare, spostare, proteggere ed eliminare i propri profili.

### 4.5 Esperienza GNOME nativa

L'interfaccia deve rispettare le GNOME Human Interface Guidelines.

L'applicazione deve comportarsi come un normale componente dell'esperienza desktop Linux.

### 4.6 Modularità

Le sorgenti esterne sono integrate mediante connettori separati dal motore centrale.

L'aggiunta o la rimozione di una sorgente non deve richiedere modifiche sostanziali all'applicazione.

### 4.7 Nessun allarmismo

Un'esposizione non equivale automaticamente a una compromissione attuale.

L'interfaccia deve distinguere chiaramente tra fatti osservati, rischi ipotizzati e azioni raccomandate.

---

## 5. Il concetto fondamentale: il profilo

Il profilo è l'unità principale di lavoro di GLeaks.

L'utente può creare un profilo personale, uno professionale o più profili separati.

Ogni profilo è un file contenitore persistente, basato su SQLite.

Esempi:

```text
personal.gleaks
professional.gleaks
family.gleaks
```

Un profilo contiene:

- Metadati.
- Identificatori digitali.
- Sorgenti configurate.
- Storico delle scansioni.
- Esposizioni rilevate.
- Relazioni tra identità ed esposizioni.
- Azioni correttive.
- Note personali.
- Stato delle verifiche.

### Gestione del file

Il formato `.gleaks` sarà un database SQLite protetto mediante cifratura.

Per impostazione predefinita, il profilo non dovrà contenere password di accesso agli account monitorati.

Le credenziali API dei provider saranno conservate preferibilmente mediante il sistema di gestione dei segreti del desktop.

### Portabilità

Il file potrà essere trasferito da un computer all'altro e aperto con un'altra installazione di GLeaks.

La cifratura richiederà una password del profilo oppure un meccanismo di sblocco configurato dall'utente.

Il formato dovrà prevedere un sistema di versionamento dello schema e migrazioni compatibili.

L'accesso contemporaneo in scrittura allo stesso file da più macchine non sarà supportato nella prima versione.

---

## 6. Identità digitali

Un profilo può contenere diversi tipi di identificatori.

### Tipologie previste

| Tipo | Esempio | Priorità |
|---|---|---|
| Email | user@example.com | MVP |
| Username | exampleuser | Fase 2 |
| Dominio | example.com | Fase 2 |
| Telefono | +39... | Fase 2 |
| URL personale | example.com/profile | Fase 3 |
| Nome e cognome | Mario Rossi | Fase 3 |
| Altri identificatori | Configurabili | Fase 3 |

L'inserimento di un identificatore non implica che tutti i connettori possano analizzarlo.

Ogni connettore deve dichiarare i tipi di dato supportati.

Per operazioni su domini o identificatori di terzi, quando necessario, dovranno essere previsti meccanismi di verifica della titolarità o dell'autorizzazione.

---

## 7. Il motore di analisi

Il motore coordina le interrogazioni, normalizza le risposte e aggiorna il profilo.

### Flusso operativo

1. L'utente apre un profilo.
2. Seleziona uno o più identificatori.
3. Avvia una verifica.
4. GLeaks determina quali connettori sono compatibili.
5. Presenta le informazioni necessarie al consenso.
6. Esegue le interrogazioni autorizzate.
7. Normalizza le risposte.
8. Confronta i risultati con lo storico.
9. Identifica eventuali nuove esposizioni.
10. Aggiorna l'interfaccia e le azioni raccomandate.

### Normalizzazione

Le diverse sorgenti possono rappresentare un evento utilizzando strutture differenti.

GLeaks dovrà adottare un modello comune di esposizione.

Esempio:

```json
{
  "source": "hibp",
  "source_event_id": "ExampleBreach",
  "title": "Example Breach",
  "event_date": "2024-01-15",
  "discovered_at": "2026-11-08T10:00:00Z",
  "data_classes": [
    "email_addresses",
    "passwords"
  ],
  "verification_status": "verified",
  "source_url": null
}
```

I dati sono illustrativi.

Un singolo evento può coinvolgere più identificatori di uno stesso profilo.

La normalizzazione deve evitare duplicati senza cancellare informazioni importanti sulla provenienza.

---

## 8. Sistema dei connettori

Il motore principale non deve contenere logiche specifiche dei singoli provider.

Ogni integrazione viene implementata come un connettore.

### Interfaccia concettuale

```python
class ExposureProvider:
    id: str
    name: str
    supported_identifiers: list[str]

    async def check(self, identifier, context):
        raise NotImplementedError
```

Questa interfaccia è puramente indicativa. Il contratto definitivo dovrà supportare configurazione, autenticazione, consenso, risultati tipizzati, errori e limitazioni.

### Metadati dei connettori

Ogni connettore dovrà descrivere:

- Identificativo stabile.
- Nome e versione.
- Licenza.
- Tipologie di identificatori.
- Modalità di trasmissione.
- Necessità di API key.
- Eventuali costi.
- Limiti di frequenza.
- Capacità di analisi.
- Attribuzione richiesta dal provider.

### Gestione degli errori

Dovranno essere distinti:

- Identificatore non presente nei risultati disponibili.
- Nessun risultato rilevato.
- Credenziali API mancanti.
- Limite di richieste superato.
- Provider temporaneamente indisponibile.
- Risposta non valida.
- Interrogazione non autorizzata.
- Errore di rete.

Un errore non deve mai essere interpretato come assenza di violazioni.

### Sicurezza dei connettori

Inizialmente saranno distribuiti soltanto connettori inclusi e revisionati insieme all'applicazione.

Un eventuale sistema di plugin di terze parti richiederà successivamente un modello di permessi, isolamento e distribuzione affidabile.

L'obiettivo è impedire che un connettore non attendibile acceda indiscriminatamente al database personale.

---

## 9. Prima integrazione: Have I Been Pwned

Have I Been Pwned (HIBP) è la fonte iniziale più appropriata per verificare indirizzi email coinvolti in violazioni note.

Il servizio offre API documentate per la consultazione di esposizioni e credenziali compromesse.

### Modalità di accesso

Le verifiche degli indirizzi email richiedono una sottoscrizione API, salvo gli specifici meccanismi di test previsti dal servizio.

Le interrogazioni possono avvenire in due modalità:

**Ricerca diretta**

L'indirizzo email completo viene comunicato al servizio.

**Ricerca mediante k-anonymity**

Il client calcola un hash dell'indirizzo e trasmette soltanto una porzione iniziale dell'hash.

La seconda modalità richiede un piano HIBP che includa questa funzionalità.

### API Pwned Passwords

HIBP dispone inoltre di una API gratuita per verificare se una password sia presente in raccolte di credenziali compromesse.

La verifica può avvenire trasmettendo soltanto un prefisso dell'hash della password.

Questa funzione non sarà inclusa nel primo MVP, ma potrà diventare un modulo separato.

La password non deve essere salvata nel profilo, registrata nei log o trasmessa in chiaro.

### Vincoli

- Rispettare condizioni d'uso e rate limit.
- Indicare esplicitamente HIBP come fonte dove richiesto.
- Non aggirare i meccanismi di autenticazione.
- Non memorizzare dati estranei restituiti dalle interrogazioni k-anonymity.
- Non presentare la copertura HIBP come esaustiva.
- Non usare un'unica chiave API condivisa pubblicamente dentro un'applicazione desktop.

**Decisione MVP:** connettore HIBP con API key fornita dall'utente e supporto alla modalità di ricerca consentita dal suo piano.

Per lo sviluppo iniziale saranno utilizzati gli account di test documentati da HIBP.

---

## 10. Il modello delle esposizioni

GLeaks deve distinguere tre concetti.

### Evento

Una violazione o pubblicazione di dati associata a un servizio.

### Evidenza

Il risultato ottenuto da una specifica fonte che collega un identificatore a un evento.

### Azione

Un intervento che l'utente può eseguire per ridurre il rischio.

Questa distinzione impedisce di confondere la presenza storica di un dato in un dataset con lo stato attuale della sicurezza dell'account.

### Stati delle azioni

```text
OPEN
IN_PROGRESS
COMPLETED
DISMISSED
```

Esempi di azioni:

- Cambiare una password potenzialmente compromessa.
- Revocare sessioni attive.
- Abilitare l'autenticazione a più fattori.
- Verificare le opzioni di recupero dell'account.
- Controllare la presenza di accessi sospetti.
- Chiedere la rimozione di informazioni esposte, quando applicabile.

Una violazione storica non viene eliminata perché l'utente ha modificato la password.

Rimane una evidenza, mentre cambia lo stato delle azioni associate.

---

## 11. Architettura applicativa

### Stack iniziale proposto

| Componente | Tecnologia |
|---|---|
| Linguaggio | Python 3 |
| Interfaccia | GTK 4 |
| Componenti GNOME | Libadwaita |
| Binding | PyGObject |
| Archivio locale | SQLite |
| Cifratura database | SQLCipher |
| Segreti | libsecret |
| Networking | Client HTTP asincrono |
| Packaging | Flatpak |
| Build | Meson |
| CI/CD | GitHub Actions o GitLab CI |
| Internazionalizzazione | gettext |

Python è una buona scelta iniziale per accelerare prototipazione e manutenzione dei connettori.

L'architettura non deve però legare permanentemente il motore di analisi all'interfaccia grafica.

### Suddivisione dei componenti

**Presentation Layer**

Finestre, navigazione, dialoghi, notifiche e visualizzazione dei risultati.

**Application Layer**

Gestione dei profili, orchestrazione delle verifiche e azioni dell'utente.

**Domain Layer**

Identificatori, eventi, evidenze, azioni e regole di classificazione.

**Infrastructure Layer**

SQLite, cifratura, chiamate HTTP, secret storage e implementazioni dei connettori.

### Esecuzione asincrona

Le interrogazioni di rete non devono bloccare l'interfaccia GTK.

Il motore deve supportare cancellazione delle operazioni, avanzamento, timeout, retry limitati e rispetto dei rate limit.

L'integrazione tra event loop asincrono e main loop GLib dovrà essere definita e testata esplicitamente.

---

## 12. Modello dati SQLite

Lo schema sarà normalizzato e versionato.

### Tabelle principali

**profiles**

Metadati del profilo, versione dello schema e impostazioni locali.

**identifiers**

Identificatori appartenenti al profilo.

Campi indicativi:

```text
id
type
value
label
created_at
enabled
```

**providers**

Catalogo dei provider e informazioni sulla loro configurazione.

**scans**

Registro delle scansioni.

```text
id
provider_id
identifier_id
started_at
completed_at
status
error_code
```

**breaches**

Eventi di violazione normalizzati.

```text
id
source
source_event_id
title
description
event_date
published_at
verified
```

**exposures**

Collegamenti tra identificatori, eventi e fonti.

```text
id
identifier_id
breach_id
first_seen_at
last_seen_at
evidence_status
```

**actions**

Azioni correttive.

```text
id
exposure_id
type
description
status
created_at
completed_at
```

**provider_observations**

Eventuali dettagli di provenienza, data, affidabilità e contenuto minimo necessario delle risposte.

### Requisiti del database

- Foreign key abilitate.
- Indici sulle ricerche frequenti.
- Transazioni per gli aggiornamenti.
- Migrazioni versionate.
- Gestione del formato tra versioni diverse.
- Deduplicazione.
- Test di integrità.
- Backup prima delle migrazioni rischiose.
- Esclusione di segreti e informazioni sensibili dai log.

Non devono essere conservate copie indiscriminate delle risposte dei provider.

---

## 13. Esperienza utente

GLeaks deve essere comprensibile anche a persone senza competenze informatiche.

### Schermata iniziale

Alla prima esecuzione vengono proposte due azioni:

**Create Profile**

Crea un nuovo archivio locale.

**Open Profile**

Apre un archivio esistente.

### Creazione profilo

Il processo deve chiedere soltanto le informazioni necessarie:

- Nome descrittivo.
- Posizione del file.
- Impostazioni di protezione.
- Primo identificatore, opzionale.

### Dashboard

Dopo l'apertura del profilo, l'utente visualizza:

- Numero di identificatori monitorati.
- Eventi conosciuti.
- Nuove evidenze.
- Azioni aperte.
- Stato delle ultime verifiche.

Le statistiche devono descrivere fatti osservabili, non produrre falsi punteggi universali di sicurezza.

### Sezione Identifiers

Permette di aggiungere, modificare, disabilitare e rimuovere identificatori.

### Sezione Exposures

Mostra gli eventi rilevati, con filtri per identificatore, fonte, stato e data.

### Dettaglio evento

Ogni evento presenta:

- Servizio interessato.
- Descrizione.
- Periodo della violazione, se noto.
- Tipologie di dati coinvolti.
- Fonte e attendibilità.
- Identificatori coinvolti.
- Azioni suggerite.
- Data dell'ultima verifica.

### Sezione Actions

Una vista dedicata permette di seguire le attività ancora da completare.

### Preferences

Contiene impostazioni per:

- Provider.
- Privacy e trasmissione dei dati.
- Credenziali API.
- Notifiche.
- Frequenza dei controlli futuri.
- Protezione del profilo.
- Lingua e opzioni applicative.

---

## 14. Requisiti di integrazione GNOME

L'applicazione deve utilizzare i componenti nativi e seguire le GNOME Human Interface Guidelines.

### Requisiti UX

- Interfaccia adattiva.
- Supporto tema chiaro e scuro.
- Navigazione da tastiera.
- Accessibilità.
- Supporto a tecnologie assistive.
- Iconografia coerente.
- Dialoghi non invasivi.
- Testi comprensibili.
- Stati vuoti informativi.
- Feedback chiaro sulle operazioni.
- Traduzioni mediante gettext.
- Gestione corretta di errori e operazioni lunghe.

### Funzioni desktop

- Apertura dei file `.gleaks`.
- Associazione MIME.
- Registrazione dell'applicazione.
- Integrazione con i file chooser.
- Notifiche desktop.
- Icona simbolica.
- Azioni principali accessibili dalla tastiera.

### Accesso al filesystem

Quando distribuita tramite Flatpak, GLeaks dovrà utilizzare i portali desktop per ottenere l'accesso ai file scelti dall'utente.

### Filosofia delle autorizzazioni

Evitare privilegi elevati, accesso indiscriminato al filesystem e permessi non necessari.

L'accesso alla rete sarà necessario per le verifiche online, ma l'applicazione dovrà spiegare chiaramente quando e perché comunica con l'esterno.

---

## 15. Sicurezza e threat model

GLeaks gestisce dati personali e informazioni relative a potenziali compromissioni.

Per questo motivo la sicurezza non può essere una funzionalità opzionale.

### Asset da proteggere

- Identificatori personali.
- Storico delle esposizioni.
- Note private.
- Chiavi dei provider.
- File del profilo.
- Backup.

### Minacce principali

1. Furto del file del profilo.
2. Accesso non autorizzato al dispositivo.
3. Compromissione di un connettore.
4. Intercettazione o divulgazione accidentale delle richieste.
5. Esposizione delle chiavi API.
6. Perdita o corruzione del database.
7. Informazioni malevole ricevute dai provider.
8. Accesso a copie temporanee del database.

### Misure

- Cifratura del database a riposo.
- Gestione separata delle chiavi API.
- Comunicazioni HTTPS con verifica TLS.
- Nessuna password personale conservata in chiaro.
- Nessun segreto nei log.
- Validazione dei dati ricevuti.
- Limitazione dei privilegi.
- Dipendenze aggiornate.
- Backup protetti.
- Test automatizzati.
- Revisione dei connettori.

La cifratura deve coprire anche i rischi collegati a copie temporanee, file ausiliari e backup.

### Limite di sicurezza

La cifratura del database non protegge completamente i dati contro un malware che abbia già compromesso la sessione desktop dell'utente.

GLeaks deve documentare chiaramente il proprio modello di minaccia.

---

## 16. Funzionamento offline

Un principio importante è la separazione tra consultazione dei dati e interrogazioni esterne.

Senza connessione Internet, GLeaks deve consentire:

- Apertura dei profili.
- Consultazione dello storico.
- Ricerca negli eventi memorizzati.
- Modifica degli identificatori.
- Gestione delle azioni.
- Esportazione dei dati.

Le scansioni online devono invece segnalare esplicitamente l'indisponibilità della rete.

I controlli già completati devono conservare la propria data: non devono sembrare aggiornati in tempo reale.

---

## 17. Privacy, responsabilità e GDPR

L'applicazione deve essere progettata per ridurre la raccolta e la diffusione dei dati personali.

### Regole iniziali

- Nessuna telemetria obbligatoria.
- Nessun account centrale.
- Nessun caricamento automatico del profilo.
- Nessuna sincronizzazione cloud attiva per impostazione predefinita.
- Consenso esplicito per le richieste ai provider.
- Minima conservazione dei dati necessari.
- Possibilità di eliminare il profilo.
- Documentazione chiara sui servizi esterni.

Il GDPR dovrà essere considerato durante la progettazione, senza assumere che un'applicazione local-first sia automaticamente esente da ogni obbligo.

Particolare attenzione andrà riservata alle verifiche su identificatori appartenenti ad altre persone, al trattamento effettuato dagli eventuali provider e alle condizioni d'uso delle fonti.

GLeaks non deve trasformarsi in uno strumento per ricercare indiscriminatamente informazioni private su terzi.

---

## 18. MVP — Versione 0.1

La prima release deve dimostrare il valore del concetto senza introdurre complessità non necessarie.

### Funzionalità obbligatorie

- Applicazione GTK 4 / Libadwaita.
- Creazione del profilo.
- Apertura e chiusura del profilo.
- Persistenza SQLite.
- Cifratura del profilo.
- Supporto a più indirizzi email.
- Configurazione del connettore HIBP.
- Integrazione autenticata con HIBP.
- Scansione manuale.
- Visualizzazione delle violazioni.
- Memorizzazione dello storico.
- Deduplicazione dei risultati.
- Indicazione della fonte.
- Azioni correttive.
- Gestione degli errori.
- Esecuzione asincrona.
- Packaging Flatpak.
- Documentazione di installazione.

### Non obiettivi della versione 0.1

- Monitoraggio continuo in background.
- Cloud proprietario.
- Account online.
- Sincronizzazione multi-dispositivo.
- Marketplace di plugin.
- Scansione del dark web.
- Motore OSINT generalizzato.
- Analisi automatica dei numeri di telefono.
- Interrogazione massiva dei motori di ricerca.
- Scansione dei file locali.
- Gestione delle password.
- Analisi con modelli linguistici.

Queste funzionalità potranno essere valutate successivamente, ma non devono ritardare la prima versione funzionante.

---

## 19. Roadmap

### Milestone 1 — Foundation

**Obiettivo:** applicazione GNOME funzionante.

Deliverable:

- Repository.
- Licenza.
- Struttura del progetto.
- Finestra principale.
- Gestione profili.
- Database e migrazioni.
- Test del modello dati.
- Flatpak di sviluppo.

### Milestone 2 — First Exposure

**Obiettivo:** completare il primo flusso di analisi.

Deliverable:

- Gestione identificatori email.
- Contratto dei connettori.
- Connettore HIBP.
- Configurazione API key.
- Scansioni.
- Risultati normalizzati.
- Gestione degli errori.
- Test con account di esempio.

### Milestone 3 — Personal History

**Obiettivo:** rendere utile lo storico.

Deliverable:

- Deduplicazione.
- Timeline delle verifiche.
- Dettagli degli eventi.
- Nuove evidenze.
- Azioni correttive.
- Esportazione dei risultati.
- Migrazioni del profilo.

### Milestone 4 — GNOME Release Quality

**Obiettivo:** preparare la release pubblica.

Deliverable:

- Verifica delle Human Interface Guidelines.
- Accessibilità.
- Traduzioni iniziali.
- Icona definitiva.
- AppStream metadata.
- Screenshot applicativi.
- Flatpak.
- Test di sicurezza.
- Documentazione.
- Release 0.1.

### Milestone 5 — Future Extensions

Possibili sviluppi:

- Altri provider.
- Monitoraggio pianificato.
- Notifiche delle nuove esposizioni.
- Supporto username.
- Supporto domini verificati.
- Verifica volontaria di password compromesse.
- Export e import estesi.
- Ricerche relative alla presenza pubblica dei dati.
- Integrazioni con strumenti di gestione dell'identità.
- Richieste di rimozione dei dati, dove possibili.

---

## 20. Struttura proposta del repository

```text
gleaks/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── meson.build
├── pyproject.toml
├── data/
│   ├── icons/
│   ├── ui/
│   ├── migrations/
│   └── metainfo/
├── src/
│   └── gleaks/
│       ├── application.py
│       ├── window.py
│       ├── domain/
│       │   ├── identifiers.py
│       │   ├── breaches.py
│       │   ├── exposures.py
│       │   └── actions.py
│       ├── services/
│       │   ├── profiles.py
│       │   ├── scanning.py
│       │   └── normalization.py
│       ├── storage/
│       │   ├── database.py
│       │   └── migrations.py
│       ├── providers/
│       │   ├── base.py
│       │   └── hibp.py
│       ├── security/
│       │   ├── secrets.py
│       │   └── encryption.py
│       └── ui/
│           ├── dashboard.py
│           ├── identifiers.py
│           ├── exposures.py
│           └── preferences.py
├── tests/
├── po/
├── packaging/
│   └── flatpak/
└── docs/
```

La struttura definitiva dipenderà dalle scelte di packaging e dal modello di gestione delle risorse GTK.

---

## 21. Strategia di distribuzione

### Prima fase

Repository open source e build di sviluppo.

### Seconda fase

Pubblicazione su Flathub, verificando i requisiti di packaging, sandbox, metadati e manutenzione.

### Terza fase

Eventuale distribuzione Snap per utenti Ubuntu.

### Quarta fase

Possibile proposta ai canali di distribuzione Ubuntu, qualora il progetto raggiunga sufficiente maturità, affidabilità e continuità di manutenzione.

**Obiettivo qualitativo:** creare un'applicazione che sembri appartenere naturalmente all'ecosistema GNOME, indipendentemente dal suo stato ufficiale.

La distribuzione ufficiale da parte di Ubuntu costituisce un obiettivo di lungo periodo e non è garantita dalla sola conformità tecnica.

---

## 22. Testing e criteri di qualità

Il progetto dovrà adottare una strategia di verifica automatizzata.

### Unit test

- Validazione degli identificatori.
- Normalizzazione delle risposte.
- Deduplicazione.
- Gestione dello stato delle azioni.
- Migrazioni database.

### Integration test

- Apertura e chiusura dei profili.
- Persistenza.
- Cifratura e sblocco.
- Connettori con risposte simulate.
- Errori di autenticazione.
- Rate limit.
- Timeout e problemi di rete.

### Test dell'interfaccia

- Primo avvio.
- Profili vuoti.
- Profili contenenti numerosi eventi.
- Navigazione tramite tastiera.
- Tema scuro.
- Dimensioni ridotte della finestra.
- Accessibilità.

### Test di sicurezza

- Assenza di segreti nei log.
- File temporanei protetti.
- Protezione delle chiavi API.
- Gestione di database corrotti.
- Gestione di risposte malevole.
- Verifica dei permessi Flatpak.

### Acceptance criteria MVP

La versione 0.1 può essere considerata completa quando un utente riesce a:

1. Installare GLeaks.
2. Creare un profilo protetto.
3. Aggiungere un indirizzo email.
4. Configurare un connettore HIBP autorizzato.
5. Avviare una scansione.
6. Consultare eventuali esposizioni rilevate.
7. Visualizzare la provenienza dei risultati.
8. Registrare le azioni intraprese.
9. Chiudere l'applicazione.
10. Riaprire il profilo senza perdita di dati.

Il flusso deve funzionare anche in assenza di esposizioni note e deve distinguere chiaramente questo caso da un errore di ricerca.

---

## 23. Rischi progettuali

### Dipendenza da provider esterni

Le API possono cambiare, introdurre costi o interrompere determinati servizi.

**Mitigazione:** connettori indipendenti e gestione esplicita delle funzionalità disponibili.

### Qualità e copertura delle fonti

Non tutte le violazioni vengono individuate o pubblicate.

**Mitigazione:** comunicare sempre che i risultati rappresentano informazioni note alla fonte, non una garanzia di assenza di rischi.

### Protezione del profilo

L'archivio concentra informazioni sensibili.

**Mitigazione:** cifratura, gestione dei segreti, minimizzazione dei dati e test di sicurezza.

### Complessità delle dipendenze GNOME

GTK, PyGObject, GLib, SQLCipher e Flatpak richiedono integrazione accurata.

**Mitigazione:** stabilizzare fin dall'inizio la build riproducibile e testare direttamente nel sandbox Flatpak.

### Esperienza utente

Il progetto potrebbe diventare troppo tecnico o generare ansia attraverso avvisi privi di contesto.

**Mitigazione:** linguaggio semplice, provenienza verificabile e azioni concrete.

### Sostenibilità open source

Le integrazioni esterne possono introdurre costi ricorrenti.

**Mitigazione:** evitare un backend centralizzato, usare API key personali e mantenere separati i servizi gratuiti da quelli a pagamento.

---

## 24. Decisioni architetturali iniziali

| Decisione | Scelta |
|---|---|
| Applicazione desktop nativa | Sì |
| GNOME come piattaforma principale | Sì |
| Python per la prima implementazione | Proposto |
| GTK 4 / Libadwaita | Sì |
| SQLite per i profili | Sì |
| Cifratura dei profili | Requisito |
| Architettura local-first | Sì |
| Backend proprietario | No |
| Account obbligatorio | No |
| Connettori modulari | Sì |
| HIBP come primo provider | Sì |
| Flatpak come prima distribuzione | Sì |
| Monitoraggio in background | Dopo MVP |
| AI/LLM | Non necessario |
| Licenza GPL-3.0-or-later | Proposta |

### Decisioni da approfondire

- Scelta e integrazione definitiva della cifratura SQLite.
- Modello di gestione della password del profilo.
- Separazione tra segreti desktop e file portabile.
- Contratto definitivo dei connettori.
- Application ID e dominio del progetto.
- Branding e collisioni con software esistente.
- Modalità di testing della distribuzione Flatpak.
- Strategie di compatibilità tra versioni del file `.gleaks`.

---

## 25. Definizione di successo

GLeaks non deve essere giudicato dal numero di provider integrati.

Il primo obiettivo è dimostrare che il concetto di *profilo personale di esposizione digitale* risulta utile, comprensibile e sostenibile.

Il progetto avrà raggiunto il suo primo traguardo quando sarà possibile:

**Creare un archivio personale, associare le proprie identità digitali, ricercare esposizioni note, conservarne lo storico e gestire le azioni necessarie senza dipendere da un servizio cloud proprietario.**

La qualità GNOME, la portabilità dell'archivio e la trasparenza delle interrogazioni sono elementi centrali del prodotto, non funzionalità accessorie.

---

## 26. Conclusione

GLeaks nasce dall'idea che il controllo della propria identità digitale non debba essere necessariamente delegato a un browser, a un motore di ricerca o a un servizio centralizzato.

Un'applicazione desktop può diventare il luogo in cui l'utente conserva la conoscenza della propria esposizione online, indipendentemente dalla piattaforma utilizzata.

Il monitoraggio delle violazioni è il punto di partenza.

La visione di lungo periodo è più ampia: costruire uno strumento libero per conoscere e gestire la propria impronta digitale.

**GLeaks — Know where your data has leaked.**