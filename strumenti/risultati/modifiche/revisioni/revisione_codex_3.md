Revisione statica; non ho rieseguito le 49 prove né il ricalcolo di sviluppo.

| Punto | Esito | Nota |
|---|---|---|
| B1 | Risolto | Ogni modifica chiude la presenza certa precedente. |
| B2 | In parte | I duplicati ricadono sulla posizione, ma gli abbinamenti ambigui non sono conteggiati separatamente. |
| B3 | Risolto | Token per chiamata e pensieri `think` condivisi sono gestiti nei casi descritti. |
| B4 | Risolto | Le esclusioni H3 sono separate per motivo. |
| B5 | Risolto | Intervalli Clopper–Pearson per esecuzione, anche con zero successi. |
| B6 | Risolto | Denominatori, intervalli assenti e valori JSON non finiti sono gestiti. |
| B7 | In parte | Una redirezione con variabile, come `>> "$P"`, non invalida il percorso noto se `$P` lo indica. |
| B8 | Risolto | Il filtro incerto è dichiarato; i tassi sono riferiti al rilascio. |
| B9 | Risolto | Sono controllati unicità, uguaglianza 30B/480B e appartenenza all’universo comune. |
| B10 | In parte | Il marcatore precede gli input held-out, ma viene dopo la lettura/hash di `misura_dev.json`, in contrasto con la §7.2. |
| B11 | In parte | Resta un errore descrittivo: righe duplicate possono far classificare un revert di debug come `flip_flop`. |
| N3 | Risolto | La §6 parla ora di «omissione nel testo». |

| Problema | Esito |
|---|---|
| 1 | Risolto |
| 2 | In parte: resta il caso della redirezione con variabile descritto per B7. |
| 3 | Risolto |
| 4 | Risolto per gli esempi segnalati |
| 5 | Risolto |
| 6 | Risolto |

### Problemi nuovi concreti

- In [formati.py](<strumenti/agenti/modifiche/formati.py:49>), se lo stesso ID compare in `no_generation` e `resolved`, `load_outcomes()` lo classifica come risolto senza segnalare il conflitto. Nei tre `results.json` attuali non ho trovato sovrapposizioni.
- In [formati.py](<strumenti/agenti/modifiche/formati.py:150>), due chiamate della stessa risposta senza ID di risposta possono contare due volte i token: con 100 token e due risultati, ne risultano 200. È una misura descrittiva, fuori da H1–H6.
- I controlli strutturali non verificano il numero atteso di esecuzioni: se entrambe le cartelle Qwen omettessero lo stesso compito, H2 userebbe un campione incompleto. Le cartelle attuali contengono 500, 500 e 489 file, come atteso.

### Verdetto: **NON PRONTA**

Blocco minimo: in [rilevatori.py](<strumenti/agenti/modifiche/rilevatori.py:190>), `>> "$P"` viene trattato come bersaglio letterale, invece che come scrittura non identificabile. Se `$P` indica un file con un blocco presente, il rilevatore può conservarne una presenza certa dopo la scrittura; un test successivo può quindi alterare l’eleggibilità o l’esito di H3/H4. La §9 richiede che una scrittura non identificabile invalidi i file noti.

Non ho aggiornato `COORDINAMENTO.md`: l’ambiente consente solo la lettura.