## BLOCCANTI

- **B2 non chiuso:** `flush()` scatta per ogni chiamata con `shared_response` assente/falso. Se un messaggio assistant contiene più `tool_calls`, `R.calls()` li restituisce uno alla volta: la seconda chiamata può quindi vedere l’output della prima e classificarlo come vista precedente. Questo viola la regola sulle chiamate parallele. ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:113>), [rilevatori.py](<strumenti/agenti/modifiche/rilevatori.py:111>))
- Il controllo “un solo percorso” conta solo i percorsi assoluti riconosciuti dalla regex: `cat /assoluto/file.py relativo.py` può passare e attribuire l’output misto al primo file. Inoltre `outputs` raccoglie solo risultati di chiamate che `R.calls()` riesce a interpretare, non ogni risultato precedente.

## NON BLOCCANTI

- **B1 e B4 chiusi.** B3 corregge le finestre più corte rispetto al conteggio normalizzato; `strip("\n")` rimuove però eventuali righe vuote ai bordi, una convenzione da chiarire se si intende il conteggio letterale.
- Stime condizionate, repliche bootstrap scartate, sei testi distinti più recenti e classe `whitespace_only` sono recepiti. Resta una lacuna di rendicontazione: senza `--out`, stdout non mostra numeratori, denominatori e repliche scartate richiesti dalla §4.

## VERDETTO

**NON PRONTA**

Non ho aperto `strumenti/risultati/` né eseguito il programma. Non ho potuto aggiornare `COORDINAMENTO.md` perché la sandbox è in sola lettura.