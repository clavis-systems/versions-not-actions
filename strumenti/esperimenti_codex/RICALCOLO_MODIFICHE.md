# Ricalcolo indipendente — modifiche agli agenti

## Perimetro e riproducibilità

Ricalcolo indipendente in `ricalcolo_modifiche.py`, a partire dalle definizioni congelate e dagli input elencati in `strumenti/risultati/modifiche/misura_heldout.inputs.json`. SHA-256 e dimensioni corrispondono per 1.502 input; l’unico percorso saltato è `misura_dev.json`, escluso dal perimetro. Nessun risultato heldout di Claude è stato consultato prima di salvare `RICALCOLO_MODIFICHE_codex.json`.

Scostamento dichiarato: per errore avevo letto §§5–8 della premessa. Claude ha chiarito che questo non invalida il ricalcolo; il codice resta indipendente, ma non sono cieco ai valori di sviluppo. Sono cieco ai valori heldout di Claude.

## Esiti meccanici e ipotesi

| Insieme | Edited | Noop | Missing | Multiple | Other | Fallimenti / chiamate |
|---|---:|---:|---:|---:|---:|---:|
| SWE-Hero R2E heldout | 1.058 | 27 | 8 | 7 | 1 | 43 / 1.100 = 3,91% |
| OpenHands Qwen 30B | 1.791 | 61 | 111 | 14 | 2 | 188 / 1.977 = 9,51% |
| OpenHands Qwen 480B | 3.273 | 88 | 59 | 28 | 15 | 190 / 3.448 = 5,51% |

- **H1 non sostenuta:** in 30B `noop` (61) non è il fallimento più frequente: `missing` è 111. La regola richiede che H1 valga in tutti e tre gli insiemi.
- **H2 sostenuta sui compiti comuni:** 500 task; differenza 30B − 480B di fallimenti per chiamata = **+4,01 punti percentuali**, IC bootstrap percentile 95% **[+2,04; +5,97] pp**. È una differenza osservata tra due configurazioni, non un effetto causale isolato della sola taglia del modello.
- **H5 sostenuta in entrambi gli insiemi Qwen:** quota di risoluzione con almeno un noop meno quota senza noop: 30B **−24,30 pp**, IC95 **[−38,92; −10,53]**; 480B **−16,75 pp**, IC95 **[−29,93; −3,45]**. Un esito è escluso per ciascun insieme perché non compare nelle liste di esito ammesse.
- **H6 non sostenuta:** SWE-Hero heldout ha 221 esecuzioni. Gli IC95 sono: fallimenti/chiamata **[2,85%; 5,02%]**, quota noop fra i fallimenti **[46,67%; 77,27%]**, esecuzioni con noop **[6,79%; 15,38%]**, esecuzioni con cerchio **[0%; 1,36%]**. Confrontati con i valori di sviluppo dichiarati nella premessa (3,31%, 58,24%, 6,33%, 1,13%), tre intervalli li contengono; quello per le esecuzioni con noop no. Compatibilità non significa equivalenza.

## Ritorni a versioni fallite

H3 resta **non valutabile**: le esecuzioni ammesse sono 2/221 in SWE-Hero (0 successi), 4/500 nel 30B (2 successi) e 5/500 nel 480B (4 successi), tutte sotto la soglia di 30. H4 resta **non valutabile**: rispettivamente 1/221, 0/500 e 1/500 esecuzioni ammesse; nessuna con entrambi gli errori nominati. Gli intervalli Clopper–Pearson e i conteggi completi per esecuzione sono nel JSON allegato.

## Opus e limiti dei dati

Opus 4.5 è presente solo come osservazioni, senza argomenti delle chiamate o identificativi. Il parser registra 1.506 osservazioni di modifica riconosciute e 9 errori meccanici riconoscibili (4 noop, 5 missing), tasso descrittivo **9/1.515 = 0,59%**. Non posso verificare dal log che ogni successo osservato corrisponda a `str_replace`; il valore è quindi un proxy, non un confronto certificato.

Il parser abbina le osservazioni OpenHands tramite `tool_call_id`, leggendo `content`; per Opus usa solo le osservazioni serializzate. SWE-Hero usa le shard 4–13 filtrate per R2E-Gym. Bootstrap: 2.000 repliche per esecuzione/task, seme 20261009. Nessun modello o benchmark è stato avviato.

## Verifiche

`webui-env\Scripts\python.exe -m unittest tests.test_ricalcolo_modifiche -v`: **7 test OK**; `py_compile`: OK. La suite completa è stata avviata, ha mostrato numerosi errori nei test eseguiti prima dell’interruzione e poi non ha dato avanzamento né output per oltre 50 secondi; interrotta, quindi esito complessivo **incompleto/non superato**. Non ho modificato test altrui.
