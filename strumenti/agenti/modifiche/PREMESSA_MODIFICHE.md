# Premessa: modifiche fallite e sprecate negli agenti che programmano

Regole fissate prima della corsa sui dati tenuti da parte, per l'articolo della Gemma 4 Developer Agent Paper
Track. Si congela con un commit; dopo, ogni cambiamento va nella sezione «Scostamenti», con data e motivo.

## 0. Precedenti e perimetro

Il controllo di novità di Codex (`strumenti/esperimenti_codex/NOVITA_VISTE_VECCHIE.md`, 09/10, 20 fonti più un
seguito) ha trovato precedenti diretti. **Non rivendichiamo come nuovi** questi punti:
- **Misurare le viste vecchie in molte esecuzioni reali.** FreshCtx (Basurto, 23/09/2026) conta le richieste con
  viste superate in 67.074 esecuzioni OpenHands con Qwen3-Coder-480B su SWE-rebench.
- **Sincronizzare o invalidare il contesto prima dell'azione:** CORVUS (arXiv 2607.22711), Concord (arXiv
  2610.05281), le ancore di Hashline.
- **Contare le modifiche fallite e il recupero, e confrontare editor e modelli:** SWE-agent (arXiv 2405.15793,
  B.3.3), Gupta et al. (arXiv 2606.17454, 153.990 traiettorie), Thakur (20/02/2026: errori, rivisite e cicli di
  modifica), Hashline, Aider.
- **Ricordare tentativi e versioni con i risultati delle prove:**
  - Reflexion e LATS: tentativo concreto più feedback dei test;
  - SWE-Search: stati con commit, diff e test, ritorno e deduplicazione;
  - GenProg: cache sorgente → esito dei test;
  - PyGGI: lista tabu delle patch già visitate.
- **Fermare gli agenti bloccati.** Lo StuckDetector di OpenHands (SDK) guarda al massimo 20 eventi del ramo attivo
  dopo l'ultimo messaggio dell'utente. Confronta azioni e osservazioni; per l'alternanza servono 6 azioni e 6
  osservazioni; la serie di errori non richiede lo stesso testo; avvisa prima di fermare. Nella versione classica
  0.62.0 le regole sono diverse.

**Cosa proviamo a sostenere**, e solo nei limiti di questa premessa:
1. **Una risorsa controllabile di incidenti** su esecuzioni pubbliche di più modelli:
   - due assi separati: l'esito meccanico dello strumento e la prova disponibile sullo stato del file;
   - denominatori espliciti, casi ignoti contati;
   - costo osservato per categoria.
2. **Un avviso candidato dell'host:** quando ricompare un blocco già tolto, anche dopo azioni diverse o lontane,
   l'host ricorda quale prova era fallita mentre quel blocco c'era.
   - Qui misuriamo solo quanto spesso l'occasione si presenta e se l'agente nomina già l'errore di allora.
   - Il beneficio non si misura in questa corsa: richiede una prova dal vivo con un confronto (§7).

## 1. Domande

1. Quanto spesso falliscono le modifiche `str_replace` nelle esecuzioni reali, e di che tipo sono i fallimenti?
2. Quando un agente riscrive una sua versione con cui una prova del programma era fallita, le sue parole mostrano
   che ricorda com'era andata?
3. Quanto spesso l'agente gira in tondo fra due versioni fallite, e in quel caso nomina i due errori?
4. Le esecuzioni con modifiche nulle risolvono il compito meno spesso? È un'associazione, non una causa.
5. Il modello più piccolo sbaglia di più, a parità di agente e di compiti?

## 2. Dati

**Sviluppo, già usato:** SWE-Hero (NVIDIA, CC-BY-4.0), frammenti 0–3.
- 10.000 esecuzioni di Qwen3-Coder-480B con OpenHands, tutte della raccolta R2E-Gym (8 progetti).

**Tenuti da parte.** Prima della corsa non è stato calcolato nessun conteggio di errori degli agenti su questi
dati; le eccezioni sono dichiarate sotto.
- **SWE-Hero, frammenti 4–13:** 24.269 esecuzioni.
  - Raccolte: R2E-Gym 221, SWE-Gym 5.859 (SWE-Gym 1.869 e SWE-Gym-Raw 3.990), SWE-rebench 18.189.
  - **Filtro incerto.** Il rapporto tecnico (arXiv 2604.01496 v2, §3.1, Trajectory Filtering) descrive
    l'esclusione delle esecuzioni con almeno tre errori dell'editor. Il testo però indica 13,2 mila traiettorie
    contro le 34.269 del rilascio. Non è attestato che i file pubblicati abbiano esattamente quel filtro.
  - I tassi di SWE-Hero si leggono come tassi di questo rilascio, **non come limiti inferiori** della popolazione
    originaria: una selezione cambia numeratore, denominatore e composizione.
- **SWE-bench Verified**, invii ufficiali con OpenHands, con l'esito di ogni compito (`results.json`):
  - Qwen3-Coder-30B-A3B-Instruct: 500 esecuzioni; nei log il modello si chiama `Qwen3-Coder-30A3-0731`;
  - Qwen3-Coder-480B-A35B-Instruct: 500 esecuzioni; nei log `Qwen3-Coder-Max-0721`;
  - Claude Opus 4.5: 489 esecuzioni; sono salvati solo i risultati degli strumenti, non le chiamate.
  - La versione di OpenHands di ogni esecuzione viene registrata dove i log la riportano.
- **Cosa ho già visto dei dati tenuti da parte:**
  - la struttura: formati, ricevute della traduzione, numero di chiamate `str_replace` (1.979 nel 30B, 3.463 nel
    480B);
  - il tasso di risoluzione pubblico;
  - la composizione per raccolta di SWE-Hero.
  - **Opus 4.5, eccezione:** controllando il formato il 09/10 ho visto i conteggi grezzi di due errori dell'editor:
    4 modifiche nulle e 5 «testo non trovato». Per Opus i risultati sono solo descrittivi.

**Lettura:** con `formati.py`. Ogni esecuzione ha una ricevuta e tutte devono essere in pareggio (descrizione in
`FORMATO_COMUNE.md`).

## 3. Rilevatori e misure

Il codice (`rilevatori.py` versione 2 e `misura.py`, con le impronte SHA-256 nel file di avvio e nei risultati)
applica le definizioni esatte della §9. Qui c'è il riassunto. Ci sono **due assi**, da non confondere.

**Esito di ogni chiamata dell'editor: riuscito, errore o sconosciuto.**
- Il risultato di una chiamata è il messaggio dello strumento con lo stesso identificativo. Senza identificativi è
  quello nella stessa posizione, se il numero dei risultati è uguale a quello delle chiamate; altrimenti manca.
- La chiamata è riuscita solo se il messaggio di successo corrisponde al comando.
- Un risultato vuoto, mancante o non riconosciuto è «sconosciuto»: non conta né come riuscito né come fallito ed è
  riportato a parte.

**Asse 1: esito meccanico di `str_replace`**, dal messaggio dell'editor:
- noop: testo nuovo uguale al vecchio («must be different»);
- missing: il testo vecchio non c'è («did not appear verbatim»);
- multiple: il testo vecchio compare più volte;
- other: ogni altro errore.

**Asse 2: prova disponibile sullo stato, solo per missing.** I testi visti sono:
- le letture riuscite del file;
- i pezzi mostrati dopo le modifiche;
- le letture semplici da bash, anche la prima di un file mai visto;
- il testo scritto dall'agente stesso.

Le classi:
- vista vecchia: il testo era in un testo visto e il file è cambiato dopo;
- errore di copia negli spazi;
- visto e non modificato;
- **non osservato nel log:** non vuol dire «inventato».

Un comando bash che può scrivere il file lo segna come «forse modificato». È una prova incerta, dichiarata come
tale.

**Modifiche nulle.**
- Cause, nell'ordine: già applicata, ripetizione, dopo un comando fallito (codice d'uscita diverso da 0, o
  un'espressione d'errore), altro.
- Esito: stesso punto, altrove nello stesso file, mai più.
- Costo osservato: le chiamate fino alla modifica riuscita successiva dello stesso file, compresa.
  - Le modifiche nulle mai seguite da una modifica riuscita sono contate a parte.
  - Mediana usuale.
  - Non è un risparmio causale.

**Ritorni (memoria delle versioni).** L'identità è il **testo del blocco dentro un percorso**, con almeno una riga
di 8 caratteri. Il resto del file e del progetto può essere diverso.

**Presenza certa (regola prudente).** La presenza di un blocco è certa dal momento in cui l'agente l'ha scritto con
un `str_replace` riuscito fino al **prossimo cambiamento qualsiasi dello stesso file**. Contano come cambiamento:
- un altro `str_replace` riuscito, anche lontano dal blocco;
- un insert, un create o un undo;
- una modifica dall'esito sconosciuto;
- un comando bash che può scrivere quel file, o file che non si possono identificare.

Il blocco appena scritto resta l'unico presente. Così una modifica che tocca il blocco solo in parte non può
lasciare una falsa presenza certa.

Un blocco tolto dal primo cambiamento di un file che nulla aveva ancora cambiato è testo originale, presente con
certezza dall'inizio. Negli altri casi l'intervallo di presenza è incerto.

**Vite di un blocco.** Ogni rimozione aggiunge un intervallo di presenza (una «vita») alla storia del blocco.

**Provenienza**, fissata alla prima comparsa: originale, dell'agente, incerta. Un ritorno a un blocco originale
resta «ritorno all'originale» anche dopo che l'agente l'ha riscritto. Quindi un ritorno è di tre tipi: ritorno
all'originale, versione propria, provenienza incerta.

**Già fallita.** Si prende la vita certa più recente in cui è stato eseguito almeno un comando di prova (`pytest`,
`python`, …).
- Se in quella vita un comando di prova è fallito, la versione è «già fallita», con l'ultimo fallimento.
- Se sono passati tutti, non lo è. Le vite senza prove e quelle incerte non contano.
- La riga fallita è l'ultima riga del risultato con un'espressione d'errore.
- Il fallimento è «d'infrastruttura» se la riga nomina un modulo, un comando o un file mancante, un tempo scaduto,
  un'uccisione, un permesso o una connessione. È «sconosciuto» se non c'è una riga fallita; altrimenti è «del
  programma».

**Altre proprietà dei ritorni:**
- **Progetto forse cambiato:** fra l'ultima rimozione e la riscrittura c'è una modifica di un altro percorso,
  oppure un comando bash che può scrivere, su qualunque percorso.
- **Ricorda:** le parole dell'agente al momento della riscrittura (la finestra del ragionamento, solo testo
  anteriore alla modifica) nominano, come parola intera, un errore (`FooError`, `FooException`) o un test
  (`test_foo`) della riga fallita di allora.
- **Cerchio:** la versione riscritta e quella che sostituisce erano fallite entrambe, con presenza certa e per un
  errore del programma.
  - Due errori diversi: gli insiemi dei nomi d'**errore** delle due righe (`FooError`, `FooException`; i nomi dei
    test non contano) non sono vuoti e non hanno nomi in comune.
  - Entrambi nominati: la finestra nomina almeno un nome d'errore di ciascuno.

**Altre misure:**
- tasso uniforme dell'editor: (noop + missing + multiple) / (modifiche riuscite + noop + missing + multiple), dai
  soli risultati. È l'unica misura confrontabile con Opus 4.5;
- ritorni indietro esatti (flip-flop) e di debug;
- modifiche solo di spazi;
- chiamate malformate;
- esiti sconosciuti;
- quota dei token spesi in chiamate `str_replace` fallite, dove ci sono i token. I token di una risposta sono divisi
  in parti uguali fra tutte le sue chiamate (anche quelle nello stesso messaggio); a una chiamata fallita va la sua
  parte. È un costo osservato;
- come sono stati abbinati chiamate e risultati: per identificativo, per posizione, oppure senza risultato.

**Statistica:**
- bootstrap percentile con 2.000 repliche e seme 20261009;
- si ricampionano le esecuzioni (per H2 i compiti), quindi i tentativi ripetuti nella stessa esecuzione non contano
  come campioni indipendenti;
- i rapporti sono somme su somme; le repliche con denominatore zero si scartano e si contano;
- per H3 e H4 l'unità è l'esecuzione, con l'intervallo esatto di Clopper–Pearson, valido anche con zero successi.

**Esito del compito:**
- risolto = 1, non risolto = 0;
- `no_generation` e `no_logs` restano fuori dall'analisi dell'esito;
- un'esecuzione che non compare in nessuna lista di `results.json` è contata come non risolta. Il loro numero e la
  riconciliazione degli identificativi vengono riportati.

## 4. Ipotesi e regole di decisione

«Insiemi Qwen» indica SWE-Hero tenuto da parte, OpenHands + Qwen3-Coder-30B e OpenHands + Qwen3-Coder-480B.

| | Ipotesi | Sostenuta se |
|---|---|---|
| H1 | La modifica nulla è il fallimento di `str_replace` più frequente | in ciascuno dei tre insiemi Qwen ci sono fallimenti e la quota di noop è strettamente più alta di ciascuno degli altri tre tipi |
| H2 | Con lo stesso agente e gli stessi compiti, il modello più piccolo fallisce di più | sui compiti comuni ai due invii, ricampionando i compiti, l'intervallo al 95% di (fallimenti per chiamata del 30B − quelli del 480B) è tutto sopra 0 |
| H3 | Quando riscrive una sua versione già fallita per un errore del programma, l'agente quasi mai nomina l'errore di allora | vedi sotto |
| H4 | Nei cerchi con due errori diversi del programma, l'agente quasi mai li nomina entrambi | come H3, sui cerchi con due errori diversi |
| H5 | Le esecuzioni con almeno una modifica nulla risolvono meno compiti | in entrambi gli insiemi OpenHands Qwen, l'intervallo al 95% di (tasso con − tasso senza) è tutto sotto 0 |
| H6 | Le misure di sviluppo sono compatibili con la stessa raccolta tenuta da parte | nelle 221 esecuzioni R2E-Gym tenute da parte, l'intervallo al 95% contiene il valore di sviluppo per: fallimenti per chiamata, quota di noop, esecuzioni con una modifica nulla, esecuzioni con un cerchio |

**Regola di H3.**
- L'unità è l'esecuzione. Sono ammesse le esecuzioni con almeno un caso che ha queste tre proprietà:
  - una versione propria riscritta, con almeno una vita certa e provata;
  - nella vita certa e provata più recente, un fallimento del programma;
  - almeno un nome d'errore o di test nella riga fallita.
- Un'esecuzione è un «successo» se in almeno uno di quei casi l'agente nomina l'errore di allora.
- H3 è sostenuta se, in ogni insieme Qwen con almeno 30 esecuzioni ammesse, il limite superiore dell'intervallo
  esatto di Clopper–Pearson al 95% è sotto il 10%.
- Le versioni proprie escluse sono contate per motivo: presenza incerta, mai provata, provata e passata, fallimento
  d'infrastruttura o sconosciuto, nessun nome.
- Anche la misura per caso, con il bootstrap, viene riportata come parte descrittiva.
- **H4** usa la stessa regola sui cerchi con due errori diversi del programma (nomi d'errore disgiunti); il
  successo è un'esecuzione in cui l'agente nomina un errore di ciascuna delle due versioni.

**Stati.** Ogni ipotesi è «sostenuta», «non sostenuta» o «non valutabile». È non valutabile quando mancano dati o
intervalli, oppure, per H3 e H4, quando nessun insieme ha almeno 30 esecuzioni ammesse. Dopo aver visto i
risultati non si aggiusta niente.

**Note:**
- H2 confronta due taglie con lo stesso agente e gli stessi compiti. I due modelli però differiscono anche per
  versione e addestramento, quindi H2 non isola la sola taglia.
- H6 misura compatibilità, non equivalenza.
- In H3 e H4 l'assenza di nomi misura un'omissione nel testo, non un limite matematico della dimenticanza.

## 5. Parti descrittive, senza ipotesi

- SWE-Hero tenuto da parte, separato per raccolta: le raccolte di sviluppo e di prova sono diverse, quindi le
  differenze possono dipendere dai compiti e non dal modello.
- Per H3: la stessa misura solo dove il progetto non è cambiato nel frattempo; la quota con progetto cambiato; le
  versioni proprie escluse, per motivo; i fallimenti d'infrastruttura, esclusi da H3 e H4.
- Come sono stati abbinati chiamate e risultati.
- Classi del testo non trovato; cause, esiti e costi delle modifiche nulle; ritorni indietro; modifiche solo di
  spazi; chiamate malformate; quota dei token; versioni di OpenHands.
- Opus 4.5: tasso uniforme dell'editor, esecuzioni con una modifica nulla, esito.
- Associazione fra cerchi ed esito.

## 6. Cautele e controesempi, dichiarati prima

- **Non è causa.** L'associazione con l'esito non è una causa: le esecuzioni lunghe hanno più occasioni di errore e
  spesso compiti più difficili.
- **I costi sono osservati.** Un replay dice quali richieste un controllo avrebbe intercettato, non cosa il modello
  avrebbe fatto dopo. Sottrarre i token storici non dà un risparmio.
- **«Nomina l'errore» è un indicatore stretto.** L'agente può ricordare senza nominarlo. H3 e H4 misurano
  un'omissione nel testo, non la memoria del modello.
- **Intenzione.** Dichiarazione esplicita, intenzione dedotta e caso ignoto restano distinti.
  - Le parole d'intenzione (lista di parole e giudice gemma4) non entrano nelle ipotesi.
  - La prova di sviluppo del 09/10 va confermata su casi annotati separati, con la stessa finestra anteriore alla
    modifica e senza usare l'esito successivo.

**Sei controesempi:**
1. **Ripristino voluto.** A→B→A può servire a riprodurre il difetto o a confrontare due ipotesi. L'avviso
   ricorderebbe, non vieterebbe; i conteggi dei ritorni non sono conteggi di spreco.
2. **Dipendenza corretta altrove.** Il blocco ricompare ma un altro file è cambiato: «allora il test fallì» non
   vuol dire «fallirà ancora». Per questo il progetto forse cambiato è segnato e misurato a parte.
3. **Errore d'infrastruttura.** Codice d'uscita 1 per una dipendenza assente, un tempo scaduto o un comando
   sbagliato non prova un difetto della versione. Questi casi sono separati ed esclusi da H3 e H4.
4. **Blocco fuori contesto.** Lo stesso testo in un'altra funzione o posizione dello stesso file non è per forza lo
   stesso tentativo. Non viene distinto: è un limite dichiarato.
5. **Test che modifica il progetto.** Un comando di prova può cambiare file. Se è riconosciuto come possibile
   scrittura, segna il progetto come forse cambiato; altrimenti la mutazione resta non osservata.
6. **Ciclo lungo con azioni diverse.** Riconoscere il ritorno non equivale a un beneficio. Il beneficio, gli
   avvisi impropri e i token aggiunti si misurano solo dal vivo.

## 7. Procedura

1. **Congelamento.** Con un commit si congelano questa premessa e il codice (`formati.py`, `rilevatori.py`,
   `misura.py`). Il file `misura_dev.json` resta fuori da git; la sua impronta SHA-256 è scritta nella §8.
2. **Una sola corsa:** `python -I strumenti/agenti/modifiche/misura.py heldout`.
   - Prima di aprire qualsiasi file d'ingresso, anche solo per calcolarne l'impronta, il programma scrive
     `misura_heldout.started` in modalità «x», con l'ora e le impronte del codice.
   - Subito dopo scrive in `misura_heldout.inputs.json` l'impronta di `misura_dev.json` e di ogni file
     d'ingresso.
   - Se il file di avvio esiste, il programma non parte.
   - Se la corsa si interrompe, il file di avvio resta. Un nuovo tentativo è uno scostamento: va scritto, con il
     motivo, e il vecchio file di avvio si conserva rinominato.
   - Anche i risultati si aprono in modalità «x».
3. **Controlli strutturali obbligatori:**
   - tutte le ricevute in pareggio;
   - nessuna chiamata `str_replace` diversa dall'azione registrata, anche quando l'azione registrata è di un altro
     tipo;
   - identificativi delle esecuzioni unici;
   - il numero atteso di esecuzioni: 10.000 (sviluppo), 24.269 (SWE-Hero tenuto da parte), 500, 500 e 489;
   - nessun identificativo in più di una lista dello stesso `results.json`;
   - riconciliazione fra gli invii SWE-bench:
     - il 30B e il 480B devono coprire gli stessi compiti;
     - gli identificativi di Opus e quelli elencati nei `results.json` devono stare dentro quell'elenco.
   - Se un controllo fallisce, le ipotesi non vengono valutate e il file dei risultati elenca i problemi.
4. **Verifica a campione dopo la corsa.**
   - 20 incidenti per ciascuna di sei categorie, presi dai tre insiemi Qwen insieme con il seme 20261010: noop,
     vista vecchia, non osservato nel log, multiple, versione propria già fallita, cerchio.
   - Programma: `campione_verifica.py`, congelato con il resto, che si rifiuta di partire prima della corsa.
     - Gli incidenti si ordinano per insieme, esecuzione e passo.
     - Si estraggono con `random.Random(20261010)`, categorie nell'ordine sopra.
     - Ogni caso porta la chiamata, il risultato e i messaggi vicini, tagliati a 400 caratteri.
   - Claude e Codex li giudicano separatamente («rilevatore corretto / sbagliato / incerto»).
   - Si riportano la precisione dei rilevatori e l'accordo fra i due.
5. Codex ricalcola in modo indipendente le misure principali partendo da questa premessa e dalla §9, senza leggere
   il codice.
6. **Prova dal vivo**, decisa dall'utente e fuori da questa corsa: confronti separati con lo stesso budget.
   - nessun avviso nuovo;
   - solo l'avviso di ricomparsa;
   - l'avviso con le prove passate;
   - l'avviso con le differenze di contesto;
   - come controlli di base: i controlli già presenti nell'editor e la rilettura forzata.
7. Ogni scostamento va nella sezione «Scostamenti».

## 8. Valori di sviluppo

Da `misura_dev.json` (SWE-Hero, frammenti 0–3), calcolati con lo stesso programma prima del congelamento.

| Misura | Conteggio | Valore | Intervallo al 95% |
|---|---|---|---|
| Fallimenti di `str_replace` per chiamata (H6) | 1.195/36.103 | 3,31% | 3,12–3,50% |
| Quota di noop fra i fallimenti (H1, H6) | 696/1.195 | 58,24% | 55,27–61,25% |
| Esecuzioni con almeno una modifica nulla (H6) | 633/10.000 | 6,33% | 5,84–6,78% |
| Esecuzioni con almeno un cerchio (H6) | 113/10.000 | 1,13% | 0,92–1,33% |
| Versioni proprie già fallite: errore nominato, per esecuzione (H3) | 2/113 esecuzioni | 1,77% | 0,22–6,25% (Clopper–Pearson) |
| Cerchi con due errori diversi: entrambi nominati, per esecuzione (H4) | 0/31 esecuzioni | 0,00% | 0,00–11,22% (Clopper–Pearson) |

- Tipi di fallimento nello sviluppo: noop 58,24%, missing 25,69%, multiple 15,90%, other 0,17%.
- Esiti sconosciuti di `str_replace`: 0. Ritorni: {'back_to_original': 509, 'retry_own': 387, 'uncertain_provenance': 374}, di cui con presenza incerta 431.
- Il file `misura_dev.json` è stato scritto il 2026-10-10T20:13:56; SHA-256 `ea676f06257b4fcfa9d439bfbd5a0d84a2dea24372defbe5a131892b15469fe1`.
- Impronte del codice: `formati.py` ac9479c8a98c…, `rilevatori.py` 67736642fa83…, `misura.py` ab9ddaa3c80f….
- Controlli strutturali sullo sviluppo: nessun problema.

## 9. Definizioni esatte

Servono per un ricalcolo indipendente. Le espressioni regolari sono in sintassi Python (`re`).

**Testi.**
- `norm(t)`: si tolgono gli a capo all'inizio e alla fine, poi gli spazi in fondo a ogni riga.
- Blocco «grande»: almeno una riga con 8 caratteri o più dopo aver tolto gli spazi ai bordi.
- `lines(t)`: l'insieme delle righe, senza spazi ai bordi, lunghe almeno 8 caratteri.
- `squash(t)`: in ogni riga gli spazi consecutivi diventano uno solo; poi si tolgono gli spazi ai bordi del testo.
- Dalle letture si tolgono i numeri di riga con `^ *\d+\t` (multilinea).

**Chiamate.**
- Si considerano solo le chiamate con argomenti JSON che sono un oggetto, nell'ordine dei messaggi; dentro un
  messaggio, nell'ordine delle chiamate.
- Il «numero di chiamata» conta queste chiamate a partire da 0 e dà l'ordine di tutto: rimozioni, prove, cambiamenti.
- Il risultato di una chiamata si cerca fra i messaggi `tool` che seguono subito il suo messaggio.
  - Se tutte le chiamate e tutti questi messaggi hanno un identificativo e gli identificativi non si ripetono, si
    abbina per identificativo.
  - Altrimenti, se i numeri coincidono, si abbina per posizione. Se gli identificativi c'erano ma si ripetevano, lo
    si conta a parte.
  - Altrimenti il risultato è vuoto.
  - Si contano le chiamate abbinate in ciascun modo.

**Ordine delle esecuzioni**, che serve al bootstrap:
- SWE-Hero: frammenti in ordine numerico, righe nell'ordine del file;
- OpenHands: cartelle dei compiti in ordine alfabetico;
- Opus: file in ordine alfabetico.

**Esito dell'editor**, controlli in quest'ordine sul risultato senza spazi iniziali:
1. Se inizia con `ERROR`, `Invalid`, `No replacement` o `Ran into`:
   - contiene `must be different` → noop;
   - contiene `did not appear verbatim` → missing;
   - contiene `[Mm]ultiple occurrences` → multiple;
   - altrimenti → other.
2. Nei primi 300 caratteri c'è `has been edited` → edited.
3. Inizia con `File created successfully` → created.
4. Inizia con `Last edit to` e nei primi 300 caratteri c'è `undone` → undo.
5. Nei primi 400 caratteri c'è ``Here's the (result of running `cat -n`|files and directories)`` → view.
6. Altrimenti → non riconosciuto.

«Riuscito» vuol dire: edited per `str_replace` e `insert`, created per `create`, view per `view`, undo per
`undo_edit`. Ogni altro esito che non sia un errore è sconosciuto.

**Comandi bash.**
- Comando di prova: `pytest|python|unittest|tox|nose|make test|npm test|go test|cargo test`.
- Fallito: se il risultato contiene `exit code (-?\d+)`, conta l'ultimo codice, ed è fallito se è diverso da 0.
  Altrimenti è fallito se contiene `Traceback|FAILED|AssertionError|Error:|error:|Exception` (FAIL).
- Riga fallita: l'ultima riga del risultato che contiene FAIL, senza spazi ai bordi, primi 120 caratteri. È vuota se
  non ce n'è una.
- Infrastruttura: la riga contiene
  `ModuleNotFoundError|No module named|command not found|[Tt]imed? ?out|Killed|Permission denied|No such file or directory|ConnectionError|MemoryError`.
- Nomi: `\b[A-Z]\w*(?:Error|Exception)\b|\btest_\w+`. Un nome è «nominato» se `\b<nome>\b` compare nella finestra.
- Lettura: il comando inizia con `cat`, `head`, `tail`, `sed -n` o `nl`. Il testo letto, senza i numeri di riga, va
  a ogni percorso assoluto nominato (`(/[\w.\-/]+\.\w+)`) e a ogni percorso noto scritto per intero nel comando,
  solo se il comando non può scrivere.
- Nel testo non trovato (asse 2) un file conta come modificato:
  - dopo un suo cambiamento riuscito o dall'esito sconosciuto;
  - dopo una scrittura bash che lo ha come bersaglio;
  - dopo una scrittura bash non identificabile, che vale per tutti i file noti.

**Scrittura da bash.**
1. Prima si tolgono le copie di descrittori e le scritture su /dev/null:
   `\d*>&\d+|&>>?\s*/dev/null|\d*>>?\s*/dev/null`.
2. Ogni bersaglio di `>>?\s*([^\s|;&<>]+)`, tolte le virgolette, viene associato al percorso noto uguale,
   o che finisce con `/` + il bersaglio senza `./` iniziale. Altrimenti resta com'è.
   - Se è vuoto o contiene `$`, un apice inverso, `*`, `?`, `{` o `[` (una variabile, una sostituzione o un modello),
     la scrittura è «non identificabile».
3. Se il comando contiene
   `sed\s+-i|\btee\b|\bmv\b|\bcp\b|git\s+(checkout|stash|apply|reset|restore|pull|merge)|\bpatch\b|open\([^)]*['\"][wa]|write_text|\bperl\s+-pi|\bblack\b|\bisort\b|\bautopep8\b`,
   sono bersagli anche i percorsi assoluti nominati e i percorsi noti nominati per intero o per nome del file.
   - Se non c'è nessun bersaglio, la scrittura è «non identificabile».
   - Dopo una scrittura non identificabile, nessun blocco è più presente con certezza e nessun blocco tolto dopo è
     più «originale».

**Ritorni.** Si elaborano le chiamate in ordine.
- Un insert, create o undo riuscito su P, un cambiamento di P dall'esito sconosciuto, o una scrittura bash con
  bersaglio P (o non identificabile): P «è stato cambiato», e nessun blocco di P (o di nessun file, per la scrittura
  non identificabile) è più presente con certezza.

Per ogni `str_replace` riuscito su P, con `old` e `new` dopo `norm`:
1. Si chiudono i «di nuovo tolto» delle versioni proprie già ritornate: il loro blocco è contenuto in `old` e non
   in `new`.
2. Se `old` è grande, si aggiunge una vita alla sua storia:
   - certa dalla chiamata in cui è stato scritto, se è il blocco presente di P;
   - certa dall'inizio (provenienza originale), se P non era mai stato cambiato e non c'era stata una scrittura non
     identificabile;
   - altrimenti incerta (provenienza incerta, se è la prima volta che il blocco compare).
   - La vita è «provata» se un comando di prova ha numero di chiamata strettamente compreso fra il suo inizio e la
     rimozione; il suo fallimento è l'ultimo comando di prova fallito in quell'intervallo.
3. Nessun blocco di P resta presente: la presenza certa finisce a ogni cambiamento del file.
4. Se `new` è grande e ha una storia in P, è un ritorno.
   - Il suo «già fallita» viene dalla vita certa e provata più recente della storia.
   - «Progetto forse cambiato» se fra l'ultima rimozione e questa chiamata c'è una scrittura bash, su qualunque
     bersaglio, o un cambiamento di un altro percorso.
5. Poi `new` diventa l'unico blocco presente di P da questa chiamata e, se non ne aveva una, riceve la provenienza
   «dell'agente».

**Finestra del ragionamento.**
- È il testo del messaggio della chiamata: il contenuto più il campo `thought` delle sue chiamate `think`.
- Prima vengono i `thought` delle chiamate precedenti della stessa risposta, cioè i messaggi segnati
  `shared_response` fino al primo della risposta, senza ripeterne il contenuto.
- Prima ancora, il testo di al massimo 3 messaggi dell'assistente precedenti, tornando indietro finché questi
  messaggi non hanno chiamate diverse da `think`.
- I pezzi si uniscono con uno spazio.

**Regole descrittive.**
- Ritorno indietro esatto (flip-flop): un `str_replace` riuscito che annulla uno precedente dello stesso file.
  - Esatto: `old` e `new` dopo `norm` uguali a `new` e `old` del precedente.
  - Dentro una finestra più larga: il `new` del precedente sta in `old`, e sostituendolo con il suo `old` si ottiene
    `new`.
  - Le righe cambiate si contano con le ripetizioni (differenza fra multinsiemi).
  - È «di debug» se ogni riga cambiata inizia con
    `print(`, `logging.`, `logger.`, `log.`, `import pdb`, `pdb.`, `breakpoint(`, `sys.stderr.write`,
    `sys.stdout.write`, `console.log`, `# DEBUG` o `traceback.print`.
- Solo spazi: `old != new` e le loro parole separate da spazi coincidono.
- Esito di una modifica nulla: «stesso punto» se un `str_replace` riuscito successivo dello stesso file ha un `old`
  che condivide una riga di `lines` con il testo della modifica nulla; «altrove» se il file è modificato dopo solo
  in altri punti; «mai più» altrimenti.

**Statistica.**
- Bootstrap: `numpy.random.default_rng(20261009).integers(0, n, size=(100, n))` per 20 blocchi, quindi 2.000
  repliche.
  - Si usa la stessa sequenza per ogni statistica dello stesso insieme.
  - Quantili: `numpy.quantile` lineare a 0,025 e 0,975.
  - H2 ricampiona i compiti comuni ai due invii con lo stesso generatore.
- Clopper–Pearson: intervallo esatto bilaterale al 95%, calcolato per bisezione (100 passi) sulla distribuzione
  binomiale.
- Mediana: quella usuale (media dei due valori centrali quando sono in numero pari).

## Scostamenti

Nessuno.
