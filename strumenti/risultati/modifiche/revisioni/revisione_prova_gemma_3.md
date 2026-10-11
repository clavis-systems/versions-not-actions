## BLOCCANTI

- **B2 — cancellazione non fail-safe.** `test_program` ignora ogni `OSError` di `os.remove(__file__)` e prosegue con l’import della soluzione. Se il file non viene cancellato, il codice del modello può leggerlo. La prova “spia” copre la cancellazione riuscita, non questo ramo. La cautela sull’introspezione in memoria è ben dichiarata; per congelare serve che un errore di cancellazione impedisca di eseguire la soluzione. [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:138>)

## NON BLOCCANTI

- **B5 chiuso.** Il preflight precede l’esecuzione e la configurazione registra le impronte di Wasmtime, `python.wasm`, `python.cwasm` e della libreria standard. In questa checkout c’è un solo `wasmtime.exe`, quindi non vedo disallineamenti nella selezione.
- **Margini delle note quasi chiusi.** `line_spans` mostra le occorrenze e la ripetizione di un no-op consiglia di cambiare `new_str`. `guard_noop` ora richiede che il testo sia stato introdotto da una modifica riuscita; resta un caso limite in cui una sottostringa di un blocco più ampio può essere attribuita come modifica già fatta.
- **Analisi e lucchetto.** Le esclusioni controllano direttamente `infra_error` ed esito incerto; le descrittive usano le coppie mantenute e riportano `error/kind` da `edit_failures`. Il controllo del lucchetto richiede `agente_gemma`, ma accetta anche un file obsoleto o un contenuto che contiene quella sottostringa.
- **Sviluppo3 è incompleto nello snapshot letto:** c’è solo `000_off.json`, con Python/0 risolto in 13 chiamate; manca la condizione ON. [sviluppo3.log](<strumenti/risultati/prova_gemma/sviluppo3.log>)

**VERDETTO: NON PRONTA**

Revisione statica: non ho avviato test, modelli, sandbox o GPU. `COORDINAMENTO.md` non è stato aggiornato perché il workspace è in sola lettura.