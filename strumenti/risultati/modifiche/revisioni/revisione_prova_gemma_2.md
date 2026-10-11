## BLOCCANTI

- **B2 — mitigazione presente, protezione non chiusa.** Il nonce è dentro `program.py`, montato insieme a `solution.py` nella sandbox ([sandbox_wasm.py](<strumenti/valutazione/sandbox_wasm.py:144>)); il controllo cerca parole sospette nelle aggiunte, ma è lessicale e aggirabile. Il codice candidato può quindi leggere il test e il nonce e simulare il successo. Per congelare, isolate il test dal codice candidato oppure limitate esplicitamente la conclusione a un esito euristico del banco, con questa sensibilità come cautela metodologica ([agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:156>), [controllo lessicale](<strumenti/agenti/modifiche/agente_gemma.py:166>)).

- **B5 — ripresa non ancora verificabile come stessa configurazione.** Salvataggio atomico e controllo di configurazione sono corretti, ma `run_config` registra solo il percorso di `wasmtime.exe`, non la sua versione o impronta; non registra neppure l’impronta della libreria standard. Se uno di questi componenti cambia allo stesso percorso, la ripresa può accettare risultati di ambienti diversi ([agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:503>)). Aggiungete gli hash/versioni o vincolate e verificate esplicitamente l’ambiente.

## NON BLOCCANTI

- **B1 chiuso:** le risposte senza strumenti contano; le chiamate oltre il limite non vengono eseguite e sono conteggiate. **B3 chiuso per gli errori previsti:** Ollama e sandbox producono un risultato infrastrutturale salvato; gli esiti incerti sono distinti ed esclusi tramite `solved=None`. **B4 chiuso:** L2, L3, bootstrap e ricampionamento degli appaiati corrispondono alla premessa; anche le chiamate dopo l’ultimo fallimento restano nel tratto L2. L’analisi non controlla direttamente `infra_error`, ma l’agente mantiene l’invariante `solved=None` ([analisi](<strumenti/agenti/modifiche/analisi_prova_gemma.py:47>), [esclusioni](<strumenti/agenti/modifiche/analisi_prova_gemma.py:149>)).

- **Note:** i casi normali sono implementati come descritto e, nel flusso ordinario, l’unica differenza ON/OFF è il testo aggiunto dall’host. Alcuni margini possono confondere: `guard_noop` può attribuire un testo a una modifica perché è una sua sottostringa; `line_span` riporta la prima occorrenza, non necessariamente quella appena modificata; la nota di ripetizione dice di cambiare `old_str` anche per un no-op con `old_str == new_str`. I test coprono i casi normali, non questi margini ([note](<strumenti/agenti/modifiche/agente_gemma.py:316>)).

- **Banco di sviluppo:** i risultati `sviluppo/` e `analisi_sviluppo.json` precedono le ultime note: 17/20 risolti per condizione, nessuna esclusione o chiamata scartata, 202/181 chiamate. Nell’ultima scansione `sviluppo2/` conteneva le coppie 0–5; il compito 15, che motivò la nota di ripetizione, non era ancora visibile. Quindi il controllo completo con le note definitive non è ancora verificabile. `fumo/` è precedente al nonce e non prova la classificazione finale.

- Per l’articolo, dichiarate che le statistiche descrittive usano solo coppie complete e precisate come produrre i tipi di errore con `rilevatori.py`: non compaiono nell’output di `analisi_prova_gemma.py`. Il lock GPU è verificato solo per esistenza, quindi un file obsoleto passerebbe il controllo.

## VERDETTO: **NON PRONTA**

Revisione statica: non ho avviato test, modelli, sandbox o GPU, né aperto risultati heldout. Non ho aggiornato `COORDINAMENTO.md`: il workspace è in sola lettura.