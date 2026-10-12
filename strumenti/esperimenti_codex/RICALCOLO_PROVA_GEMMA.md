# Ricalcolo indipendente — prova Gemma

## Perimetro

Ho letto i 288 log `*_on/off.json` della corsa completata in `strumenti/risultati/prova_gemma/prova/`. L’adattatore deriva gli esiti nascosti dai campi della singola corsa e controlla la coerenza con il flag `solved`; ricostruisce chiamate e risultati dai messaggi, abbinando gli ID quando disponibili. Non ho aperto `analisi_prova_gemma.py`, né eseguito codice dei log. Il mio output JSON era salvato prima di leggere l’analisi di Claude.

Le 144 coppie sono complete e non ci sono esclusioni.

## L1–L3

| Misura | Risultato indipendente | Decisione |
|---|---|---|
| L1: task risolti | acceso 124/144, spento 117/144; 10 vittorie e 3 sconfitte; McNemar bilaterale p = 0,092285; differenza quota +4,86 pp, IC bootstrap 95% [0,00; +9,72] pp | **Non sostenuta** (p ≥ 0,05) |
| L2: chiamate di recupero | spento 426, acceso 251; differenza media per task acceso − spento = −1,2153, IC95 [−1,7502; −0,7292] | **Sostenuta** |
| L3: fallimenti ripetuti | spento 213, acceso 90; differenza media per task acceso − spento = −0,8542, IC95 [−1,3057; −0,4583] | **Sostenuta** |

La sensibilità per aggiunte sospette non cambia L1: nessun task è segnalato (`open(`, `sys.`, `exit(`, `inspect`).

## Descrittive

Gli esiti di `str_replace` coincidono con quelli pubblicati: acceso 180 edited, 128 missing, 29 multiple, 9 noop, 4 other; spento 164 edited, 245 missing, 27 multiple, 7 noop, 8 other. Sono uguali anche le chiamate (1.441/1.584), i `finish` (129/121), le chiamate scartate (0/0), il tempo (4.026,8/4.450,2 s) e i token totali (5.936.286/6.728.285).

Le note dell’host acceso ricostruite dai messaggi coincidono per categoria: 36 già applicate, 46 suggerimenti di testo vicino, 29 occorrenze multiple, 5 noop già presenti, 4 noop identiche, 46 testi rimossi da una modifica, 77 chiamate ripetute e 4 ritorni a una versione fallita. Spento: nessuna nota.

## Confronto con l’analisi pubblicata

Conteggi, esiti, p-value, medie, intervalli, decisioni e descrittive coincidono. Al primo passaggio gli intervalli L2/L3 differivano: avevo ordinato lessicograficamente `Python/100` prima di `Python/20`. Ho corretto l’ordine numerico dei task (20–163), come richiede l’ordine sperimentale; i due IC ora coincidono esattamente. L’analisi di Claude lascia `L1_sensitivity_suspicious_as_unsolved` nullo; essendo la lista dei sospetti vuota, il ricalcolo esplicito non modifica le vittorie, sconfitte o p-value.

## Verifiche e file

10 test mirati passano (`python -m unittest tests.test_ricalcolo_prova_gemma -v`) e `py_compile` passa. Nessun modello, GPU o codice del modello è stato eseguito. Il JSON indipendente completo è `RICALCOLO_PROVA_GEMMA_codex.json`; lo script riproducibile è `ricalcolo_prova_gemma.py`.
