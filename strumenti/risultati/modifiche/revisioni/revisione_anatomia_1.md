## BLOCCANTI

- **B1 — L’argomento mancante può selezionare la prova.** `where` è facoltativo e qualunque valore diverso da `dev`, anche un refuso o `None`, seleziona `heldout` ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:127>), [anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:143>)). Renderlo obbligatorio e limitarlo a `dev|heldout` prima del congelamento.

- **B2 — La ricostruzione di ciò che l’agente ha visto è incompleta e può attribuire testi al file sbagliato.** Il rilevatore riconosce solo certi comandi all’inizio della stringa e percorsi assoluti; letture relative o concatenate possono sfuggire. Inoltre, l’output di `cat A B` viene associato a entrambi i file ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:94>), [rilevatori.py](<strumenti/agenti/modifiche/rilevatori.py:72>)). Le chiamate parallele nella stessa risposta sono poi elaborate in sequenza: una vista può sembrare già nota quando è stata emessa insieme alla `str_replace` ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:93>)). Questi casi possono alterare esclusione delle viste vecchie, campione e provenienza.

- **B3 — La ricerca ammette finestre più corte.** Quando il testo visto ha meno righe di `old_str`, `max(1, …)` forza comunque il confronto con una finestra parziale, che può superare 0,8. Il campione così ottenuto non rispetta la regola dichiarata delle finestre con lo stesso numero di righe ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:46>)).

- **B4 — A2 non misura la provenienza da “altrove”.** Il codice verifica se la riga compare in qualunque testo registrato, senza posizione o versione. Un match non dimostra che sia stata copiata da un’altra zona; vecchie versioni della stessa zona e righe ricorrenti possono gonfiare il conteggio ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:109>)). Riformulare A2 come corrispondenza lessicale osservata oppure definire come identificare la posizione d’origine.

## NON BLOCCANTI

- Le soglie di A1 e A2 sono numericamente falsificabili. Il bootstrap aggrega casi e righe per corsa, coerentemente con la premessa; specificare che la stima è condizionata alle corse eleggibili e riportare denominatori e repliche con denominatore zero scartate da `rate` ([misura.py](<strumenti/agenti/modifiche/misura.py:190>)). I 30 casi e le 72 righe di sviluppo restano evidenza esplorativa; evitare generalizzazioni oltre il modello e la coorte dichiarati.

- La deduplicazione delle ultime sei viste conserva la posizione della prima occorrenza, quindi una vista ripetuta di recente può non rientrare nella ricerca. Inoltre, `squeeze()` rimuove ogni whitespace: descriverei la classe come “solo differenze di whitespace”, senza implicare che siano sempre semanticamente irrilevanti ([anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:106>), [anatomia_copie.py](<strumenti/agenti/modifiche/anatomia_copie.py:57>)).

## VERDETTO

**NON PRONTA.**

Revisione statica: non ho eseguito il programma o test né aperto `strumenti/risultati/`. Non ho aggiornato `COORDINAMENTO.md` perché il filesystem è in sola lettura.