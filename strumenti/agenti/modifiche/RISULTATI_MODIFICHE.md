# Risultati della corsa unica sui dati tenuti da parte (10/10/2026)

**Fonte.** La corsa segue la premessa `PREMESSA_MODIFICHE.md`, congelata nel commit `a936baa` (etichetta
`congelamento-modifiche-2026-10-10`) dopo la quarta revisione di Codex, che ha detto «PRONTA PER IL CONGELAMENTO».

**Corsa.** `misura.py heldout`, una sola volta, dalle 20:23:14 alle 20:26:11.
- Controlli strutturali: nessun problema. Le ricevute sono tutte in pareggio, gli identificativi riconciliati e il
  numero di esecuzioni è quello atteso (24.269, 500, 500, 489).
- Impronte: `misura_heldout.json` ec4ba34f…, campione di verifica `verifica_campione.json` 58c7a728…

**Scostamenti dalla premessa:** nessuno. Lo script `riassunto.py`, aggiunto dopo il congelamento, legge soltanto
il file dei risultati.

## Ipotesi

| | Esito | Numeri |
|---|---|---|
| H1, noop il fallimento più frequente | **non sostenuta** | SWE-Hero 57,2% e 480B 46,3% sì; nel **30B prevale missing (59,0%)**, noop 32,4% |
| H2, il modello piccolo fallisce di più | **sostenuta** | 30B 9,50% contro 480B 5,49% per chiamata; differenza appaiata +4,0 punti [2,0; 6,0] su 500 compiti |
| H3, l'agente quasi mai nomina l'errore di allora | **sostenuta** | SWE-Hero: 2 esecuzioni su 272 (0,74%; Clopper–Pearson fino a 2,63%). 30B e 480B sotto le 30 esecuzioni ammesse (3 e 15): non valutabili lì |
| H4, nei cerchi con due errori diversi non li nomina entrambi | **sostenuta** | SWE-Hero: 0 su 88 (fino a 4,11%) |
| H5, chi fa una modifica nulla risolve meno compiti | **sostenuta** | 30B −24,3 punti [−38,9; −10,5]; 480B −16,8 punti [−29,9; −3,5]. Associazione, non causa |
| H6, sviluppo compatibile con R2E-Gym tenuto da parte | **non sostenuta** | 3 valori su 4 compatibili. Le esecuzioni con una modifica nulla sono 10,86% [6,79; 15,38] contro 6,33% nello sviluppo (221 esecuzioni) |

## Parti descrittive principali

**Tasso uniforme dell'editor** (l'unico confrontabile fra tutti):

| Insieme | Tasso | Intervallo |
|---|---|---|
| 30B | 9,41% | |
| 480B | 5,08% | |
| SWE-Hero | 3,47% | |
| Claude Opus 4.5 | 0,59% | [0,20; 1,07] |

Per Opus i conteggi grezzi erano già stati visti: è una parte solo descrittiva.

**Testo non trovato, «non osservato nel log».**

| Insieme | Quota dei missing |
|---|---|
| 30B | 86,5% |
| SWE-Hero | 71,4% |
| 480B | 54,2% |

Le viste vecchie sono 25,4% dei missing nel 480B, 13,6% in SWE-Hero e 12,6% nel 30B.

**Cause delle modifiche nulle in SWE-Hero:** già applicata 22,6%, dopo un comando fallito 23,4%, ripetizione 1,9%,
altro 52,0%. Mediana di 2 chiamate fino alla modifica riuscita successiva; 780 su 2.158 non sono mai seguite da
una modifica riuscita dello stesso file.

**SWE-Hero per raccolta** (esecuzioni con una modifica nulla): SWE-Gym 10,9%, SWE-Gym-Raw 9,0%, SWE-rebench 7,6%,
R2E-Gym 10,9%.

**Token spesi in `str_replace` fallite:** 0,89% (30B) e 0,78% (480B). È un costo diretto piccolo; quello indiretto
non è misurato.

**Esito con un cerchio meno senza:** 30B −52 punti su sole 5 esecuzioni; 480B −8 punti, con un intervallo che
comprende lo 0.

**Tasso di risoluzione dei compiti giudicati:** 30B 51,7%, 480B 69,7%, Opus 78,6%.

## Prossimi passi della premessa

- §7.4, verifica a campione: 120 incidenti, giudicati separatamente da Claude e da Codex (C2).
- §7.5: ricalcolo indipendente di Codex (C1).
- §7.6: prova dal vivo, che decide l'utente.

## Analisi esplorativa dopo la corsa (non prevista dalla premessa)

`esplora_mai_visto.py`: da dove viene il testo «non osservato nel log»?

| Insieme | Casi | Copia approssimata di un testo già visto (somiglianza ≥ 0,8) |
|---|---|---|
| Sviluppo SWE-Hero | 207 | 77% |
| 30B | 96 | 95% |
| 480B | 32 | 78% |

- Quasi mai viene dalla descrizione del compito o da una propria modifica fallita.
- Lettura: il modello scrive il testo «a memoria», invece di copiarlo; il modello piccolo lo fa di più.
- Guardiano candidato: mostrare il testo vero più simile, con le righe. Va provato dal vivo.
