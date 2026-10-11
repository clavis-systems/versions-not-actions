## BLOCCANTI

- **B1 — `undo_edit` è escluso.** `formati.editor_outcome` riconosce l’esito `undo`, ma il filtro di [stato_azione.py](<strumenti/agenti/modifiche/stato_azione.py:95>) ammette solo `str_replace`, `insert` e `create`. Un annullamento riuscito non entra quindi nei ritorni o nei cicli; l’edit successivo può apparire come cambiamento non tracciato. Includere l’undo usando gli stati prima/dopo, oppure escluderlo esplicitamente e contarlo come dato non valutabile.

- **B2 — «invisibile» sovrastima ciò che sfugge a Graphectory.** La definizione del lavoro usa nodi distinti per azione e argomenti, ma conserva anche occorrenze, esiti, osservazioni e archi temporali. Un fallimento con azione nuova non è una ricorrenza del nodo, ma il suo esito resta rappresentato. Limitare la tesi a «non rappresentato come ripetizione di nodo o ciclo esplicito di stato». [Definizione di Graphectory](https://arxiv.org/html/2512.02393v3#S2)

- **B3 — S3 non specifica l’automa usato per il confronto.** Nel lavoro citato gli stati dipendono dall’ultima attività estratta e i cicli dalla ricorrenza delle etichette. La regola «ogni edit successivo sullo stesso file» non stabilisce se `create`, `insert` e `str_replace` condividano un’etichetta, né come contino gli edit su file diversi. Fissare la proiezione e calcolare i cicli su quella. [Costruzione dell’automa, §3.3](https://arxiv.org/html/2608.23670v1)

## NON BLOCCANTI

- **N1 — Chiarire il bersaglio statistico.** `misura.rate` calcola un rapporto delle somme: è una quota pesata per eventi, non la quota di corse con quella proprietà. Specificare che si usa il limite inferiore dell’intervallo percentile bootstrap a due code; segnalare le sei verifiche e che la divisione ordinata per ID non autorizza generalizzazioni oltre queste coorti.

- **N2 — Stati non recuperabili e chiamate senza risultato.** Gli edit senza stato aumentano `edits_without_state`, ma non entrano in S3; una tool call senza risultato viene ignorata senza contatore. Inoltre, dopo uno stato mancante, il codice azzera `current` ma conserva `texts`, che può rendere obsoleto il replay successivo. Dichiarare l’eventuale condizionamento agli edit ricostruibili e riportare gli esclusi. [Gestione degli stati mancanti](<strumenti/agenti/modifiche/stato_azione.py:108>)

- **N3 — Precisare identità e cautele.** La chiave dell’editor usa sei argomenti; `formati.py` conserva anche `is_input`. Verificare se possa cambiare l’azione e documentare la proiezione usata. Esplicitare quali risultati sono veri per costruzione; un ritorno di un file non implica un ritorno del repository, e l’associazione con la risoluzione non è causale.

**Revisione statica:** non ho eseguito programma o test e non ho aperto `strumenti/risultati/`.

**VERDETTO: NON PRONTA.**