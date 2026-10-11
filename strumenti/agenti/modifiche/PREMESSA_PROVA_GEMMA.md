# Premessa: prova dal vivo con Gemma come agente, guardiano acceso e spento

**Stato: CONGELATA il 10/10/2026 alle 22:40,** tag `congelamento-prova-gemma-2026-10-10`.
- La revisione 4 di Codex (`revisione_prova_gemma_4.md`) dice: «PRONTA PER IL CONGELAMENTO».
- Impronte SHA-256 dei file come girano:

  | File | SHA-256 |
  |---|---|
  | `agente_gemma.py` | `dbb70bc73f870a90603657fea3aed384d20abf07e2e43f066223e92067343520` |
  | `analisi_prova_gemma.py` | `e27de06953575f4b907feb18f0a707e0548d3441c72f538080c717c4e0512134` |
  | `formati.py` | `ac9479c8a98c494f630c39e278f4b6914a76a05be15cee67eaf14e4e27600c24` |
  | `rilevatori.py` | `67736642fa833775858219cfafbf244a8855106b197d03d92beb7442321b4165` |
  | dataset (parquet) | `ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075` |

- Ogni cambiamento da qui in poi è uno scostamento e si scrive in fondo.

Storia delle bozze:
- La bozza 1 è stata rivista da Codex (`strumenti/risultati/modifiche/revisione_prova_gemma_1.md`, «NON PRONTA», 5
  punti bloccanti). La bozza 2 li ha corretti.
- La bozza 2 è stata rivista da Codex (`revisione_prova_gemma_2.md`, «NON PRONTA», 2 punti bloccanti: B2 e B5).
  La bozza 3 li ha corretti.
- La bozza 3 è stata rivista da Codex (`revisione_prova_gemma_3.md`, «NON PRONTA», 1 punto bloccante: la
  cancellazione del file delle prove doveva bloccare la soluzione se non riesce). Questa bozza lo corregge (§7).
- La prova di funzionamento su 2 compiti di sviluppo è fatta (§6).

## 1. Domanda

Gli avvisi dell'host, ricavati dallo studio sulle traiettorie (`RISULTATI_MODIFICHE.md`), aiutano un modello piccolo
che lavora come agente a correggere il codice?

## 2. Materiale

**Modello.** `gemma4:e4b-it-qat` in Ollama, sul PC dell'utente.
- Parametri: temperatura 0, seme 1, contesto 16.384 token, al massimo 1.024 token per risposta, ragionamento
  spento.
- Funziona solo se esiste il lucchetto della GPU, nomina `agente_gemma` e non è più vecchio di 24 ore: altrimenti il
  programma si rifiuta di partire.

**Compiti.** HumanEvalFix Python (bigcode/humanevalpack, licenza MIT, 164 compiti; impronta in
`esterni/humanevalpack/MANIFEST.md`).
- Ogni compito diventa un file `solution.py`: la funzione con l'errore (dichiarazione, docstring e corpo difettoso)
  in mezzo a 6 funzioni HumanEval corrette.
  - Le funzioni corrette sono quelle degli indici (i + 7·j) mod 164, senza nomi ripetuti.
  - Servono a dare alle modifiche occasioni di sbagliare: è una scelta dichiarata, non il formato originale.
  - Possono essere soluzioni corrette di altri compiti di prova. Ogni corsa però è una conversazione nuova, senza
    memoria delle altre, quindi nulla passa da un compito all'altro.
- **Sviluppo:** compiti 0–19, usati solo per controllare il banco.
- **Prova:** compiti 20–163, cioè 144.

**Agente.** `agente_gemma.py`.
- Strumenti: `view`, `str_replace` (semantica OpenHands), `run_tests` (le prove d'esempio del compito, nella
  sandbox WASM) e `finish`.
- Al massimo 20 chiamate. Una risposta senza strumenti conta come chiamata e riceve un invito a usarli.
- Se una risposta chiede più strumenti di quante chiamate restano, quelli in più non vengono eseguiti e si contano
  (`dropped_calls`).

**Esito.** Alla fine le prove complete e nascoste del compito girano nella sandbox.
- Il programma delle prove cancella il proprio file prima di importare la soluzione, così il codice del modello non
  può leggere dal disco né le prove né il nonce. È verificato nella sandbox vera da una prova automatica: un codice
  «spia» non trova il file.
- Se la cancellazione non riesce, la soluzione non viene eseguita. Si registra un errore della sandbox: il compito è
  escluso e la corsa si ferma.
- **Risolto:** codice d'uscita 0 e la riga «HIDDEN TESTS PASSED» con un codice casuale della corsa (nonce).
- **Non risolto:** un errore Python (traceback), oppure il limite di tempo o di output della sandbox.
- **Incerto:** qualsiasi altro caso, per esempio uscita 0 senza la riga giusta. Il compito si esclude e si conta.
- Il codice Python del modello e del dataset gira solo nella sandbox. Ollama e la lettura del file del dataset
  restano sul PC.

## 3. Condizioni

| Condizione | Risultati degli strumenti |
|---|---|
| Spento | Messaggi in stile OpenHands |
| Acceso | Stessi messaggi, più una nota dell'host |

Le note dell'host con il guardiano acceso:
- **chiamata ripetuta,** prima di ogni altra nota: se la stessa identica chiamata (stesso file, stesso testo vecchio
  e nuovo) è già fallita sulla stessa identica versione del file, «l'hai già mandata al passo N e fallì allo stesso
  modo; ripeterla non può funzionare: cambia old_str».
- **modifica nulla:** «l'hai già fatta al passo N» se il testo sta in una modifica riuscita precedente e nel file;
  altrimenti «sono identici: scrivi come devono diventare le righe».
- **testo mancante,** in quest'ordine:
  1. se è la stessa identica modifica (stesso testo vecchio e nuovo) già riuscita al passo N: «l'hai già fatta al
     passo N; il testo nuovo ora è alle righe X–Y; non ripeterla: lancia le prove o guarda il file», senza altri
     consigli. Se una modifica successiva ha poi cambiato quel testo, lo dice e chiede di guardare il file;
  2. se il testo vecchio era nel file e una modifica del modello l'ha tolto: «era nel file fino alla tua modifica
     al passo N»;
  3. poi il testo vero più simile nel file, con le righe (finestra di uguale lunghezza, somiglianza difflib sulle
     righe senza spazi ai bordi);
  4. se è una copia quasi esatta (somiglianza almeno 0,8, la stessa soglia dello studio), le prime 2 righe che
     differiscono, con gli spazi resi visibili, e se differiscono solo per gli spazi lo dice.
- **più occorrenze:** per ogni occorrenza il numero di riga, la funzione che la contiene e la riga intera, con
  l'invito ad aggiungere righe vicine, per esempio la riga intera da cambiare.
- **ritorno:** dopo una modifica riuscita il cui testo, di almeno una riga da 8 caratteri, era già nel file durante
  una prova fallita ed era poi stato tolto: «era già nel file al passo N; allora la prova fallì con: …». Se anche il
  testo sostituito era nel file durante una prova fallita con un altro errore, si mostrano i due errori insieme.

Per ogni compito girano entrambe le condizioni. L'ordine è casuale e dipende solo dal seme (20261011) e dal compito,
qualunque intervallo si lanci. Tutto il resto è identico.

## 4. Misure e ipotesi (sui 144 compiti di prova, appaiati per compito)

Le definizioni esatte sono nel codice di `analisi_prova_gemma.py`, con le sue prove.
- Una **chiamata** è un'unità del limite di 20: una chiamata di strumento, o una risposta senza strumenti.
- Ogni `str_replace` si classifica con `formati.editor_outcome`, come nello studio: riuscita (`edited`), oppure uno
  dei fallimenti noop, missing, multiple, other_error.

| | Misura | Ipotesi | Regola |
|---|---|---|---|
| L1 (principale) | Compiti risolti | Acceso ≥ spento | Test di McNemar esatto bilaterale sulle coppie discordanti, p < 0,05, con più vittorie che sconfitte del guardiano. Si riporta anche l'intervallo bootstrap della differenza della quota di risolti |
| L2 (secondaria) | Chiamate «di recupero» di una corsa: le chiamate fatte mentre c'è una `str_replace` fallita non ancora seguita da una riuscita. Si conta quella riuscita, non il fallimento che apre il tratto | Acceso < spento | Intervallo bootstrap al 95% della differenza media per compito (acceso − spento) tutto sotto 0 |
| L3 (secondaria) | Fallimenti ripetuti di una corsa: fallimenti di `str_replace` la cui `str_replace` precedente era fallita con lo stesso tipo | Acceso < spento | Come L2 |

- L2 e L3 sono secondarie: non si corregge per la molteplicità, e l'articolo lo dice.

**Parti descrittive:**
- tipi di esito di `str_replace` per condizione;
- note dell'host per tipo;
- compiti risolti da spento ma non da acceso (possibili danni), e il contrario;
- chiamate, `finish`, chiamate scartate, tempo e token;
- tipi di fallimento di Gemma con `rilevatori.edit_failures` (tipo di errore / causa), calcolati da
  `analisi_prova_gemma.py`: le sue traiettorie usano la stessa forma comune;
- tutte le parti descrittive usano solo le coppie complete, cioè i compiti non esclusi.

**Statistica:**
- bootstrap sui compiti con reinserimento, 2.000 repliche, `numpy.random.default_rng(20261011)`, intervallo
  percentile;
- McNemar esatto: test binomiale con p = 1/2 sulle coppie discordanti, bilaterale;
- **esclusioni:** un compito si esclude da tutti i confronti, prima del ricampionamento, se una delle due corse manca,
  ha un errore dell'infrastruttura o un esito incerto. Le esclusioni si contano e si elencano;
- **controllo di sensibilità:** si elencano le corse in cui le righe aggiunte dal modello contengono parole sospette
  (lettura di file, uscita forzata, introspezione: `open(`, `sys.`, `exit(`, `inspect`…). L1 si ricalcola contando
  come non risolte quelle corse.

**Potenza.** Il test di McNemar guarda solo le coppie discordanti, cioè i compiti risolti in una sola condizione.

| Coppie discordanti | Vittorie del guardiano necessarie per p < 0,05 |
|---|---|
| 10 | 9 |
| 20 | 15 |
| 30 | 21 |
| 40 | 27 |

Quindi si vedono solo effetti netti. Un risultato nullo non prova che l'effetto manchi.

## 5. Cautele

- **Contaminazione.** HumanEval è noto e probabilmente visto in addestramento; HumanEvalFix non è codice reale a
  più file.
- **Un solo modello, un solo campione per condizione** (temperatura 0).
- **I file allungati** sono una scelta per mettere alla prova le modifiche.
- **L'esito è un controllo del banco, non una garanzia contro un imbroglio voluto.** Prove nascoste e codice del
  modello girano nello stesso processo, come nella valutazione standard di HumanEval.
  - Il modello non vede mai le prove nascoste durante la corsa, e il file delle prove sparisce prima che il suo codice
    parta.
  - Un codice scritto apposta potrebbe però ancora trovare prove e nonce nella memoria del processo (introspezione)
    e fingere il successo. Non lo escludiamo: lo cerchiamo.
  - Le difese sono il nonce, l'elenco delle parole sospette e il controllo di sensibilità (§4). In più ogni corsa
    risolta con parole sospette si legge a mano prima dell'analisi.
  - L'articolo lo dice con queste parole.
- **Le note sono state migliorate dopo aver visto i compiti di sviluppo** (§6): prima 2, poi tutti e 20. È lo scopo
  dei compiti di sviluppo, e lo dichiariamo. Per questo i risultati sui compiti di sviluppo non contano come prova.

## 6. Procedura

1. **Prova di funzionamento** su 2 compiti di sviluppo, con le due condizioni: fatta il 10/10. Tutte e 4 le corse
   hanno risolto il compito, in circa 40 secondi l'una.
   - Nel compito 1 acceso, Gemma ha rifatto 4 volte la stessa modifica già riuscita. Ogni volta il testo vecchio
     mancava, perché l'aveva già sostituito lei.
   - La nota di allora mostrava il testo più simile e diceva «copia il testo esatto dal file», cioè la spingeva a
     riprovare.
   - Da qui nascono le note 1, 2 e 4 del testo mancante (§3).
2. **Correzioni solo del banco,** con nuove prove su dati inventati, poi la revisione di Codex.
   - Controllo del banco sui 20 compiti di sviluppo con le due condizioni: fatto il 10/10
     (`strumenti/risultati/prova_gemma/sviluppo/`).
     - Risolti 17 su 20 in tutte e due le condizioni. Chiamate di recupero: 45 da spento, 25 da acceso.
     - Nel compito 15 Gemma ha mandato 9–10 volte la stessa chiamata, con un testo presente due volte nel file, in
       tutte e due le condizioni.
     - Da qui nascono la nota della chiamata ripetuta e le righe intere nella nota delle più occorrenze (§3).
   - `sviluppo2/` è un nuovo controllo con quelle due note, interrotto a metà perché superato dalla bozza 3.
   - Controllo completo sui 20 compiti di sviluppo con il banco della bozza 3 (commit `f5b1cb8`):
     `strumenti/risultati/prova_gemma/sviluppo3/`, analisi in `analisi_sviluppo3.json`.
     - Nessuna esclusione, nessuna parola sospetta, nessuna chiamata scartata.
     - Risolti: 17 da spento, 18 da acceso (il compito 15).
     - Chiamate di recupero: 45 contro 22. Fallimenti ripetuti: 19 contro 1.
     - Le note sono state messe a punto su questi compiti, quindi questi numeri non sono una prova.
     - Un difetto visto e lasciato così: dopo «era nel file fino alla tua modifica al passo N», il testo più simile
       può essere una riga di un'altra funzione. Sarebbe stato più utile mostrare cosa ha messo quella modifica. Lo
       annotiamo per una versione futura, non lo cambiamo adesso.
   - La bozza 4 aggiunge solo il blocco di sicurezza se il file delle prove non si cancella, e la scadenza del
     lucchetto. Il percorso normale non cambia; è provato dalle prove automatiche, anche nella sandbox vera.
   - Dopo il congelamento, una prova di funzionamento sui compiti di sviluppo 0–1 con il banco congelato
     (`fumo_congelato/`).
3. **Congelamento** con un commit.
4. **Corsa sui compiti 20–163,** con il lucchetto della GPU, in una o più notti.
   - Ogni risultato registra la configurazione:
     - impronta del modello in Ollama, versione di Ollama, parametri;
     - impronte SHA-256 del programma, del dataset e di `sandbox_wasm.py`;
     - impronte di `wasmtime.exe`, dell'interprete WASM (`python.wasm` e la sua versione precompilata) e della
       libreria standard impacchettata.
   - Ogni risultato si scrive intero in un file a parte, poi si rinomina. Un file finale è sempre completo e non si
     sovrascrive mai.
   - Se la corsa si interrompe, riprende saltando i file già scritti, solo se hanno la stessa configurazione;
     altrimenti si ferma. La ripresa si dichiara.
   - Un errore di Ollama o della sandbox si registra nel risultato di quel compito, che resta escluso, e ferma la
     corsa.
5. **Analisi** con `analisi_prova_gemma.py` secondo §4; ricalcolo indipendente di Codex.

## 7. Revisioni di Codex: cosa è cambiato

**Revisione 1.**

| Punto | Correzione |
|---|---|
| B1: limite di chiamate superabile | Gli strumenti oltre il limite non si eseguono e si contano |
| B2: prove nascoste leggibili | Nonce nella riga di successo; parole sospette elencate; controllo di sensibilità; cautela dichiarata |
| B3: esclusioni non tracciabili | Errori di Ollama e della sandbox registrati nel risultato; esito incerto separato; la corsa si ferma |
| B4: L2, L3 e bootstrap non definiti | Definizioni esatte in §4 e nel codice dell'analisi, con prove |
| B5: ripresa non sicura | Configurazione in ogni risultato; scrittura intera poi rinomina; ripresa solo con configurazione uguale |
| Non bloccanti | Funzioni di contesto (§2); cosa gira nella sandbox (§2); endpoint principale e secondarie (§4); potenza (§4); versioni e impronte (§6); lucchetto controllato; la prova reale salta solo se manca la sandbox |

**Revisione 2.**

| Punto | Correzione |
|---|---|
| B2: protezione non chiusa | Il file delle prove si cancella prima di importare la soluzione, verificato nella sandbox vera. Il limite che resta (introspezione in memoria) è dichiarato come cautela (§5), con lettura a mano delle corse risolte con parole sospette |
| B5: ambiente non vincolato | Impronte di `wasmtime.exe`, `python.cwasm` e della libreria standard impacchettata nella configurazione (§6) |
| Margini delle note | «Già fatta» solo se una modifica del modello ha messo quel testo nel file; tutte le posizioni del testo nuovo, non solo la prima; per una ripetizione di modifica nulla il consiglio è «cambia new_str» |
| Non bloccanti | Le parti descrittive usano solo coppie complete; i tipi di `rilevatori.py` sono nell'analisi; il lucchetto deve nominare `agente_gemma`; l'analisi esclude anche direttamente per errore dell'infrastruttura o esito incerto |

**Revisione 3.**

| Punto | Correzione |
|---|---|
| B2: cancellazione non sicura | Se il file delle prove non si cancella, il programma si ferma prima di importare la soluzione; il banco lo registra come errore della sandbox e ferma la corsa. Prova automatica dedicata |
| Lucchetto vecchio accettato | Il lucchetto deve avere meno di 24 ore |
| «Già fatta» per una parte di un blocco più grande | Lasciato così: la frase resta vera, perché quella modifica ha messo quel testo nel file |

**Revisione 4** (solo il diff della bozza 4): nessun punto bloccante, «PRONTA PER IL CONGELAMENTO».
- Il lucchetto vecchio esattamente 24 ore, o con una data futura, è accettato: la premessa ora dice «non più vecchio
  di 24 ore».
- La prova del blocco di sicurezza simula l'errore della sandbox, non lo provoca davvero.

## Scostamenti

1. **Interruzione e ripresa della corsa** (prevista da §6, qui dichiarata).
   - L'utente ha chiesto di fermare tutto il 10/10 alle 23:32.
   - La corsa si è fermata dopo i compiti 20–91: 144 file completi, nessun file parziale.
   - È ripresa l'11/10 alle 17:27 con lo stesso comando, dopo il riavvio del server Ollama (stessa versione 0.32.13,
     stesso modello `ee665637…`).
   - Il programma ha controllato che i 144 file già scritti avessero la stessa configurazione e li ha saltati.
     Registro della ripresa: `prova_ripresa.log`.
2. **Ora del congelamento.** Lo stato dice «alle 22:40», ma il commit del congelamento (`610a9dd`) è delle 22:36.
