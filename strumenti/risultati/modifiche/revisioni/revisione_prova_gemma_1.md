## BLOCCANTI

- **B1 — Limite di chiamate superabile.** Il limite viene controllato prima della risposta del modello; se questa contiene più tool call del budget residuo, il ciclo le esegue tutte. Il banco può quindi superare le 20 chiamate dichiarate. [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:291>)

- **B2 — Le prove nascoste sono leggibili dal codice candidato.** Il runner scrive i test in `program.py` e monta l’intera cartella, inclusa `solution.py`, come `/sandbox`. Il codice valutato può leggere il sorgente delle prove durante l’esecuzione: il risultato hidden non viene inviato a un altro turno LLM, ma la segretezza rispetto alla soluzione non è garantita. [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:115>) · [sandbox_wasm.py](<strumenti/valutazione/sandbox_wasm.py:130>)

- **B3 — Esclusioni infrastrutturali non tracciabili.** Gli errori Ollama e `SandboxUnavailable` interrompono la corsa senza produrre un esito; altri `ok=False` vengono registrati come semplice fallimento. Non si può applicare e ricalcolare l’esclusione appaiata promessa. [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:293>) · [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:335>)

- **B4 — L2/L3 e bootstrap non sono pienamente definiti.** Mancano regole univoche per adiacenza e tipi in L3, conteggio delle finestre di recupero in L2, statistica bootstrap e intervallo da usare. Va inoltre chiarito come trattare le esclusioni nel resampling. [PREMESSA_PROVA_GEMMA.md](<strumenti/agenti/modifiche/PREMESSA_PROVA_GEMMA.md:54>)

- **B5 — La ripresa può accettare risultati incompleti o mescolare corse diverse.** Ogni JSON già presente viene saltato senza validare configurazione o provenienza; un’interruzione durante la scrittura può lasciare un file parziale che verrà poi considerato completo. [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:363>)

## NON BLOCCANTI

- Le condizioni sono strutturalmente identiche salvo le note: ogni `run_task` ha una conversazione nuova e non riceve l’esito dell’altra condizione. La canonica del compito corrente è esclusa; però il contesto pesca dall’intero dataset, quindi alcuni prompt contengono canoniche di altri compiti heldout. Dichiarare questo limite o usare un pool separato. [agente_gemma.py](<strumenti/agenti/modifiche/agente_gemma.py:94>)

- Il codice candidato e i test vengono eseguiti in WASM con rete disabilitata e limiti di risorse. Ollama e il caricamento del Parquet restano sull’host: precisare che è il codice Python del candidato e del dataset a girare in sandbox.

- Per l’articolo: indicare un endpoint primario e chiarire se L2/L3 sono esplorativi o se si corregge la molteplicità; la stima di potenza va giustificata sui discordanti. Registrare anche versioni e digest del modello, di Ollama e del runtime WASM. Lo script documenta il lucchetto GPU ma non lo verifica; il test reale trasforma qualunque eccezione in uno skip.

**Verdetto: NON PRONTA.** Revisione statica; non ho avviato modello, sandbox o test.