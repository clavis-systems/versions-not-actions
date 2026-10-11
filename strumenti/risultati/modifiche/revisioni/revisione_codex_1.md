Revisione statica dei testi forniti: nessun accesso ai dati. Gli strumenti locali non hanno consentito di leggere il coordinamento o eseguire Python.

**BLOCCANTI**

1. **B1 — `revisits()`: storia delle versioni.** `alive_since[p].get(old, 0)` attribuisce a blocchi nuovi fallimenti precedenti alla loro introduzione. Modifiche parziali, `create`, `insert`, `undo` e bash non aggiornano correttamente la storia. Questo può inventare cerchi e versioni fallite. Tracciare intervalli verificabili di presenza; classificare come indeterminati quelli non ricostruibili. Inoltre, `A→B→A→C→A` riclassifica l’originale A come versione propria: conservarne separatamente la provenienza.

2. **B2 — `calls()` / `editor_outcome()`: falsi successi.** Risultati vuoti o errori non riconosciuti diventano successi perché `error_type()` restituisce `None`. Inoltre, tutte le chiamate di un messaggio ricevono lo stesso risultato successivo. Abbinare tramite `tool_call_id` e distinguere successo riconosciuto, errore ed esito sconosciuto.

3. **B3 — `translate_events()` / memoria e token.** Nelle risposte con più chiamate, le successive perdono il ragionamento comune: H3/H4 possono registrare false omissioni. Il confronto per sottostringa riconosce anche `test_foo` dentro `test_foobar`. Conservare il contesto della risposta e confrontare nomi completi. Anche i token, assegnati tutti alla prima chiamata, richiedono una misura esplicitamente definita per risposta oppure un’allocazione riproducibile.

4. **B4 — H3: denominatore incoerente.** Il codice considera soltanto versioni fallite con nomi estraibili; la premessa parla di tutte le versioni proprie già fallite. Anche la soglia di 30 cambia. Fissare denominatore, esclusioni, soglia e conclusione coerenti, riportando i casi non classificabili.

5. **B5 — `rate()`: intervalli degeneri.** Con zero menzioni, il bootstrap produce `[0,0]` e sostiene automaticamente H3/H4. Non dimostra una quota inferiore al 10%: con 0/30 casi indipendenti, il limite superiore binomiale bilaterale al 95% è circa 11,6%. Preregistrare un metodo valido ai bordi e rispettoso delle esecuzioni aggregate, oppure rendere questi casi non valutabili.

6. **B6 — `hypotheses()` / denominatori zero.** H1 favorisce `noop` nei pareggi e risulta sostenuta persino senza fallimenti. Fissare esplicitamente pareggi e denominatore positivo. `between_sets()` può produrre `NaN`; H5/H6 possono fallire con esiti o intervalli assenti. Gestire lo stato “non valutabile”, registrare le repliche invalide e vietare valori JSON non finiti.

7. **B7 — Misure descrittive.** `edit_failures()` ignora una prima lettura bash di un percorso ancora sconosciuto, falsando le classi del testo mancante. `noops()` ignora un semplice `exit code 1` e calcola i turni dagli indici dei messaggi, contando anche messaggi liberi. Registrare le letture iniziali, usare `failed()` e contare direttamente i turni dichiarati.

8. **B8 — §§2,6: censura.** La selezione non garantisce limiti inferiori dei rapporti per chiamata. Esempio: conservata un’esecuzione con 1/10 errori, esclusa una con 3/100; osservato 10%, completo 3,64%. Descrivere tassi condizionati alla selezione, senza garantire la direzione della distorsione.

9. **B9 — Ricevute e copertura.** Il pareggio viene riportato, senza essere imposto; discrepanze degli argomenti e ricostruzioni scompaiono dai risultati. Rendere obbligatorie le verifiche strutturali, conservare le anomalie e riconciliare identificativi, numerosità ed esiti. Un identificativo sconosciuto non deve diventare automaticamente `unresolved`.

10. **B10 — §7 / `main()`: congelamento e corsa unica.** L’apertura `"x"` avviene dopo tutti i calcoli: un’interruzione permette un nuovo tentativo senza traccia. Registrare atomicamente l’avvio prima della lettura e fissare la procedura per interruzioni. Congelare anche `misura_dev.json`, manifest degli input e codice effettivamente eseguito. Dopo le correzioni, ricalcolare lo sviluppo prima del congelamento.

11. **B11 — §§3,7: ricalcolo indipendente.** “Le definizioni esatte sono il codice” non consente il controllo richiesto senza leggerlo. Esplicitare normalizzazione, provenienza e durata dei blocchi, finestra, regex, scelta e troncamento della riga fallita, denominatori, ordinamento, generatore casuale, quantili ed esclusioni.

**NON BLOCCANTI**

- **N1 — H2 e bootstrap:** verificare l’appaiamento dei compiti fra invii; per inferenza sui compiti condivisi serve un ricampionamento appaiato. Valutare anche eventuali esecuzioni ripetute dello stesso compito.
- **N2 — Costi:** la mediana restituita è quella superiore (`[1,3] → 3`). Usare la mediana usuale e dichiarare l’esclusione dei casi senza modifica successiva.
- **N3 — Interpretazione:** H6 misura compatibilità, non equivalenza; l’assenza di nomi misura omissione testuale, senza garantire un limite matematico sulla dimenticanza.
- **N4 — Accessi preliminari:** non emerge un’ulteriore sbirciata dal codice fornito; la storia degli accessi non è verificabile qui.

**VERDETTO: NON PRONTA.**