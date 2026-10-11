| Punto | Esito |
|---|---|
| B2 | **Risolto:** gli abbinamenti posizionali dopo ID duplicati hanno una categoria distinta in [rilevatori.py](<strumenti/agenti/modifiche/rilevatori.py:107). |
| B7 | **Risolto:** una redirezione come `>> "$P"` diventa non identificabile e invalida le presenze certe ([rilevatori.py](<strumenti/agenti/modifiche/rilevatori.py:194)). |
| B10 | **Risolto:** il marcatore viene scritto prima di aprire gli input; `misura_dev.json` è il primo input nel manifest ([misura.py](<strumenti/agenti/modifiche/misura.py:491)). |
| B11 | **Risolto:** le righe cambiate sono confrontate come multinsiemi ([rilevatori.py](<strumenti/agenti/modifiche/rilevatori.py:171)). |

Anche i tre problemi nuovi sono risolti: i conflitti tra liste bloccano la valutazione, gli ID delle chiamate raggruppano i token senza ID di risposta e i conteggi attesi delle esecuzioni sono controllati strutturalmente. Non ho trovato altri problemi concreti che invalidino H1–H6 o impediscano il ricalcolo.

**Verdetto: PRONTA PER IL CONGELAMENTO.** Revisione statica: non ho rieseguito prove o ricalcolo. Non ho potuto aggiornare `COORDINAMENTO.md` perché l’ambiente è in sola lettura.