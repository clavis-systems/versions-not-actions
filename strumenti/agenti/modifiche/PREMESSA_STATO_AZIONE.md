# Premessa: stato, non azione

**Stato: CONGELATA** l'11/10/2026, tag `congelamento-stato-azione-2026-10-11`. La revisione 3 di Codex
(`revisione_stato_azione_3.md`) dice: «PRONTA PER IL CONGELAMENTO». Ogni cambiamento da qui in poi è uno scostamento.
- La bozza 1 è stata rivista da Codex (`strumenti/risultati/modifiche/revisione_stato_azione_1.md`): «NON PRONTA»,
  3 punti bloccanti.
- La bozza 2 li ha corretti; la revisione 2 (`revisione_stato_azione_2.md`) ha detto «NON PRONTA», con 3 punti
  bloccanti. Questa bozza li corregge (§7).

## 1. Domanda

I lavori precedenti disegnano la traiettoria di un agente di programmazione come grafo di **azioni**:
- *concrete*, dove il nodo è la chiamata con il tipo e gli argomenti (Graphectory, 2512.02393). Il grafo conserva
  anche le occorrenze, gli esiti, le osservazioni e gli archi nel tempo;
- *astratte*, dove il nodo è un'etichetta dell'attività (per esempio gli automi di 2608.23670).

Noi la disegniamo come grafo di **versioni del file**: il nodo è il contenuto del file, l'arco è una modifica
riuscita, una modifica fallita è un anello sul nodo.

La domanda: quanti ritorni a uno stesso contenuto, e quanti giri a vuoto, **non si presentano come ricorrenza di un
nodo** nei grafi di azioni concrete? E quanti cicli dei grafi per etichetta **non sono ritorni** ma progressi?

Il contributo è **misurare la grandezza di queste differenze** fra rappresentazioni, sugli stessi registri. Non
diciamo che i grafi di azioni «non vedono» gli esiti: diciamo che non mostrano un ritorno come ciclo o nodo
ripetuto. Non è una novità di meccanismo: in parte gli effetti sono veri per costruzione (§5).

## 2. Materiale

- **Dati:** le traiettorie OpenHands su SWE-bench Verified di Qwen3-Coder 30B e 480B, 500 corse ciascuno. Sono gli
  stessi file dello studio congelato `PREMESSA_MODIFICHE.md`, letti con `formati.py`.
- **Contenuto del file:**
  - OpenHands registra il file prima e dopo ogni modifica riuscita, compresi gli annullamenti (`undo_edit`).
  - Per un file creato senza contenuto registrato, si usa il suo `file_text`.
  - Una modifica fallita non cambia il file.
  - Una modifica di cui non si può conoscere il contenuto si conta (`edits_without_state`), e la ricostruzione di
    quel file riparte dal contenuto noto successivo. Le misure sono quindi condizionate alle modifiche
    ricostruibili, e le esclusioni si riportano.
  - Lo stato «file assente» non è rappresentato. Un annullamento che toglie un file appena creato non ha contenuto
    registrato: si esclude e si conta (`undo_without_state`).
  - Si distinguono le chiamate senza alcun messaggio di risultato da quelle con un risultato vuoto.
- **Divisione:** in ogni insieme le corse sono ordinate per id dell'istanza.
  - Sviluppo: le prime 50, su cui sono state fissate le definizioni.
  - Prova: le altre 450.
  - Le conclusioni valgono per queste coorti, non oltre.
- **Gemma:** le 288 corse della prova dal vivo (`prova_gemma/prova/`). Qui il contenuto si ricostruisce
  esattamente rifacendo le modifiche sul file di partenza. È una parte descrittiva.
- **Programma:** `stato_azione.py`, con le prove `test_stato_azione.py`.

## 3. Definizioni

- **Modifiche:** i comandi dell'editor `str_replace`, `insert`, `create` e `undo_edit`.
- **Identità dell'azione** (proiezione concreta): nome dello strumento più gli argomenti che contano.
  - Per l'editor: command, path, old_str, new_str, file_text, insert_line.
  - Per bash: il comando. Altri campi, come `is_input`, non contano.
  - Un'azione è «ripetuta» se una chiamata identica è già avvenuta nella corsa, cioè se è una ricorrenza di un
    nodo del grafo di azioni concrete.
- **Proiezione astratta:** ogni chiamata riceve un'etichetta.
  - EDIT per ogni modifica di qualsiasi file;
  - VIEW per la lettura con l'editor;
  - BASH per i comandi;
  - altrimenti il nome dello strumento.
- **Identità dello stato:** SHA-256 del contenuto del file modificato, file per file.
  - Se il contenuto visto prima di una modifica è diverso dall'ultimo noto, qualcos'altro ha cambiato il file (per
    esempio bash): è un cambiamento non tracciato. Si conta, e si conta a parte se riporta il file a un contenuto
    già avuto.
- **Ritorno:** una modifica riuscita che riporta il file a un contenuto che aveva già avuto prima nella corsa. È
  **non ricorrente** se l'azione non era ripetuta: nel grafo di azioni concrete non si presenta come ricorrenza di
  un nodo, né quindi come ciclo.
- **Anello (tentativo bloccato):** una modifica fallita (noop, missing, multiple), con il file che resta com'era. È
  **non ricorrente** se l'azione non era ripetuta: nel grafo di azioni concrete è un nodo nuovo, non un giro.
- **Ciclo di etichetta:** ogni EDIT dopo il primo della corsa è una ricorrenza dell'etichetta, quindi un ciclo del
  grafo astratto. La modifica che lo chiude può essere:
  - un *progresso* (contenuto nuovo);
  - un *ritorno* (contenuto già avuto);
  - un *fallimento* (la modifica non riesce);
  - *nessun cambiamento* (riesce ma lascia lo stesso contenuto);
  - *ignota* (contenuto non noto).
  - I cicli «noti» sono progressi, ritorni, fallimenti e nessun cambiamento.
- **S3 misura la nostra proiezione grossolana** (un'unica etichetta EDIT). Non è la ricostruzione dell'automa di
  2608.23670, che estrae simboli dalle chiamate e ha classi di stato basate sull'ultima attività. Il confronto con
  Graphectory riguarda solo la ricorrenza dei nodi: quel grafo conserva argomenti, esiti e osservazioni, quindi un
  ritorno non è un'informazione persa, è solo non mostrata come ciclo.

## 4. Ipotesi e regole (parte di prova, per ciascun insieme 30B e 480B)

| | Ipotesi | Regola |
|---|---|---|
| S1 | La maggior parte dei ritorni è non ricorrente | Limite inferiore dell'intervallo bootstrap al 95% della quota maggiore di 0,5 |
| S2 | La maggior parte degli anelli è non ricorrente | Come S1 |
| S3 | La maggior parte dei cicli di etichetta noti è un progresso | Come S1 |

- **Intervallo:** percentile a due code, bootstrap sulle corse, 2.000 repliche, seme 20261009 (`misura.rate`, lo
  stesso dello studio congelato).
- **Quote:** sono rapporti delle somme, cioè pesate per eventi, non quote di corse.
- **Repliche vuote:** le repliche bootstrap con denominatore zero (nessun evento nelle corse estratte) si scartano
  dal percentile e si contano (`invalid_replicates`). Nello sviluppo: S2 per il 30B, 85 su 2.000.
- **Verifiche:** sono sei (3 ipotesi per 2 insiemi), senza correzione per la molteplicità, e lo diciamo.
- **Parti descrittive:**
  - corse con almeno un ritorno;
  - compiti risolti con e senza ritorni: un'associazione, non una causa;
  - cambiamenti non tracciati, e quanti sono ritorni (per esempio `git checkout`);
  - annullamenti, modifiche senza contenuto o non riconosciute, chiamate senza risultato;
  - le stesse misure sulle corse di Gemma, per condizione.

**Valori di sviluppo** (prime 50 corse per insieme):

| Insieme | S1 | S2 | S3 | Corse con ritorni | Non tracciati (ritorni) |
|---|---|---|---|---|---|
| 30B | 8/8 | 5/5 | 311/324 (0,96; [0,94, 0,98]) | 7 | 39 (5) |
| 480B | 22/25 (0,88; [0,74, 1,00]) | 24/25 (0,96; [0,87, 1,00]) | 496/546 (0,91; [0,88, 0,94]) | 12 | 139 (24) |

## 5. Cautele

- **Lo stato è il singolo file, non tutto il repository.** Un ritorno di un file non è un ritorno del repository.
- **Ciò che bash cambia si vede solo alla modifica successiva.** Per questo i cambiamenti non tracciati si
  contano, e i loro ritorni si riportano a parte.
- **Le proiezioni sono le nostre.** Una proiezione concreta che astrae di più gli argomenti avrebbe più
  ricorrenze. Per questo riportiamo i due estremi: azione completa ed etichetta.
- **In parte vero per costruzione, ma non sempre.**
  - Un annullamento fatto con `str_replace` ha argomenti scambiati rispetto alla modifica che annulla. Di solito è
    non ricorrente, ma non sempre: in una sequenza A → B → A → B l'ultima modifica ripete un'azione già vista.
  - Un fallimento seguito da un tentativo diverso è non ricorrente per quel tentativo, salvo che quell'azione sia
    già comparsa prima nella corsa.
  - Il valore sta nella grandezza, misurata sui registri veri: quanto spesso succede e quanto pesa.

## 6. Procedura

1. Revisione di Codex della bozza e di `stato_azione.py`.
2. Congelamento con un commit e un tag.
3. Una sola corsa sulla parte di prova e sulle corse di Gemma. Ogni nuova corsa è uno scostamento e si dichiara.

## 7. Revisioni di Codex: cosa è cambiato

**Revisione 1.**

| Punto | Correzione |
|---|---|
| B1: `undo_edit` escluso | Incluso fra le modifiche, con il contenuto prima e dopo; si contano gli annullamenti |
| B2: «invisibile» troppo forte | Ora «non ricorrente»: non si presenta come ricorrenza di nodo o ciclo. Si dichiara che il grafo di azioni conserva esiti e osservazioni (§1, §3) |
| B3: automa non specificato | Proiezione astratta esplicita, con l'etichetta EDIT per ogni file. Cicli di etichetta su tutte le modifiche, classificati in progresso, ritorno, fallimento e ignoti (§3) |
| N1 | Bersaglio statistico, due code, sei verifiche, generalizzazione limitata alle coorti (§2, §4) |
| N2 | Le chiamate senza risultato e le modifiche senza contenuto si contano. Dopo un contenuto ignoto la ricostruzione del file riparte da zero. Misure condizionate alle modifiche ricostruibili (§2) |
| N3 | Proiezioni documentate, compreso `is_input`. Gli effetti veri per costruzione sono elencati. File e repository sono distinti, e l'associazione non è una causa (§3, §5) |

**Revisione 2.**

| Punto | Correzione |
|---|---|
| B1: «vero per costruzione» troppo forte | Tolto «sempre». Si spiega quando un'azione inversa può essere ricorrente (§5) |
| B2: stato «file assente» | Non rappresentato: gli annullamenti senza contenuto si escludono e si contano (§2) |
| B3: cosa confronta S3 | S3 misura la nostra proiezione grossolana, non l'automa del lavoro citato. Il confronto con Graphectory è limitato alla ricorrenza dei nodi (§3) |
| N1: modifica senza cambiamento | Nuova categoria «nessun cambiamento», fuori dai progressi, con una prova automatica |
| N2: repliche con denominatore zero | Regola dichiarata, e conteggi riportati (§4) |
| N3: risultato assente o vuoto | Si contano a parte (§2) |

**Revisione 3:** nessun punto bloccante. N3, l'ultimo non bloccante, è chiuso prima del congelamento: un risultato
vuoto si conta anche quando il messaggio ha metadati. È solo un conteggio descrittivo.

## Scostamenti

1. **Dichiarazione aggiunta dopo la corsa (11/10, 21:15): S2 non era alla cieca.**
   - Prima di scrivere questa premessa, alle 18:00 circa, lo script esplorativo `esplora_idee.py` aveva contato su
     tutte le 500 corse di ciascun insieme le `str_replace` fallite identiche a una fallita prima sulla stessa
     versione del file: 24 su 186 (30B) e 11 su 175 (480B). È quasi il complemento di S2.
   - S1 e S3 non erano mai stati calcolati sulla parte di prova.
   - Inoltre lo studio congelato `PREMESSA_MODIFICHE.md` aveva già prodotto conteggi aggregati sugli stessi
     registri.
   - Me l'ha fatto notare un revisore indipendente (un agente Claude separato) durante il controllo del repository
     pubblico. Lo dichiaro qui e nell'articolo.
