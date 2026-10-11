## BLOCCANTI

- **B1 — “Vero per costruzione” è troppo forte.** In §5, righe 107–110, un inverso `str_replace` o un fallimento seguito da un tentativo diverso non sono necessariamente azioni mai viste prima nella corsa. Il codice controlla tutta la storia (`seen_actions`), quindi sequenze come A→B→A possono rendere ricorrente l’inverso. Distinguere il confronto con l’azione immediatamente precedente dalla non ricorrenza globale, oppure togliere “sempre”. [Premessa](<strumenti/agenti/modifiche/PREMESSA_STATO_AZIONE.md:107>) · [codice](<strumenti/agenti/modifiche/stato_azione.py:109>)

- **B2 — Lo stato “file assente” non è rappresentato.** Se `undo_edit` rimuove un file appena creato, `translate_events` non conserva i metadati perché richiede `old_content` e `new_content` entrambi presenti; il misuratore classifica poi l’esito come privo di stato e scarta lo stato corrente. Non conta quindi quell’undo come transizione nota, e non incrementa `undo_edits`. Definire un valore `ABSENT` oppure escludere esplicitamente questi casi e limitarne le conclusioni. [formati.py](<strumenti/agenti/modifiche/formati.py:185>) · [codice](<strumenti/agenti/modifiche/stato_azione.py:135>)

- **B3 — Precisare cosa confronta S3.** La proiezione propria con un’unica etichetta `EDIT` è dichiarata, ma non coincide direttamente con l’automa citato: quel lavoro estrae simboli dalle chiamate e costruisce una FSM le cui classi di stato sono basate sull’ultima attività. S3 va presentata come misura della proiezione grossolana scelta qui, non come ciclo già misurato nell’automa del lavoro precedente. Il confronto con Graphectory è corretto se circoscritto alla ricorrenza del nodo: il grafo conserva anche argomenti, esiti e osservazioni, quindi non si deve suggerire che il ritorno sia informazione irrecuperabile. [Automata from Agent Traces](https://arxiv.org/html/2608.23670) · [Graphectory](https://arxiv.org/html/2512.02393)

## NON BLOCCANTI

- **N1 — Edit senza cambiamento.** A `stato_azione.py:152–155`, ogni modifica con stato noto che non è un ritorno diventa progresso, anche se il contenuto finale coincide con quello corrente. La definizione richiede contenuto nuovo; aggiungere una categoria o escludere questo caso. I test non lo coprono.

- **N2 — Dettaglio bootstrap da dichiarare.** `misura.rate` elimina le repliche con denominatore zero dal percentile e le conta. Specificare questa regola nella premessa e riportare quei conteggi. Rapporti delle somme, bootstrap per corsa e soglia sono altrimenti coerenti con l’obiettivo dichiarato.

- **N3 — Risultato vuoto vs. risultato assente.** `calls_without_result` tratta un contenuto vuoto senza metadati come chiamata senza risultato; il codice non distingue l’assenza del messaggio tool da un messaggio presente ma vuoto.

**VERDETTO: NON PRONTA.** Revisione statica sul commit `6986281`; non ho eseguito il programma o i test e non ho aperto `strumenti/risultati/`. Non ho aggiornato `COORDINAMENTO.md` perché il filesystem è in sola lettura.