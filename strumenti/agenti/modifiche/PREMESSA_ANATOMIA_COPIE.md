# Premessa: anatomia degli errori di copia

**Stato: CONGELATA** l'11/10/2026, tag `congelamento-anatomia-2026-10-11`. La revisione 5 di Codex
(`revisione_anatomia_5.md`) dice: «PRONTA PER IL CONGELAMENTO». Le forme attaccate `-n10` e `-c+10` sono ammesse.
Ogni cambiamento da qui in poi è uno scostamento.
- La bozza 1 è stata rivista da Codex (`strumenti/risultati/modifiche/revisione_anatomia_1.md`): «NON PRONTA», 4
  punti bloccanti.
- La bozza 2 li ha corretti in parte; la revisione 2 (`revisione_anatomia_2.md`) ha detto «NON PRONTA», con B2 non
  chiuso. La bozza 3 l'ha corretto in parte; la revisione 3 (`revisione_anatomia_3.md`) ha detto «NON PRONTA».
  Questa bozza chiude gli ultimi punti (§7).

## 1. Domanda

Quando un agente scrive a memoria il testo da sostituire (`old_str`) e la sostituzione fallisce perché quel testo
non c'è, in che cosa la sua copia differisce dal testo vero? Sono soprattutto spazi, come si legge spesso
(CODESTRUCT 2604.05407; la discussione su Hashline), o righe con parole diverse e righe in più o in meno?

## 2. Materiale e definizioni

- **Programma:** `anatomia_copie.py`.
- **Testi visti di un file:**
  - le viste dell'editor;
  - i frammenti mostrati dopo le modifiche;
  - i propri file creati e i propri `new_str`;
  - le letture con bash «pulite»: l'**intero** comando, su una sola riga, è `cat`/`nl` con eventuali opzioni,
    `head`/`tail` con eventuale `-n N`, `-c N` o `-N` (mai un numero da solo), oppure `sed -n 'A,Bp'`, seguito da **un solo** percorso assoluto e da nient'altro.
  - I risultati di una risposta del modello diventano «visti» solo dopo tutte le chiamate di quella risposta: le
    chiamate parallele non vedono i risultati l'una dell'altra.
  - Una risposta è un messaggio dell'assistente con tutte le sue chiamate, più i messaggi successivi segnati come
    parte della stessa risposta (`shared_response`).
- **Casi:** chiamate `str_replace` fallite con «did not appear verbatim» il cui `old_str`:
  - non compare tale e quale in nessun testo visto di quel file, né (senza spazi ai bordi) in nessun messaggio di
    risultato precedente alla risposta in corso, di qualsiasi strumento. Altrimenti è una vista vecchia, magari arrivata da una lettura che non
    ricostruiamo, non un errore di copia;
  - è una copia quasi esatta di un testo visto: la finestra migliore con **esattamente** lo stesso numero di righe,
    confrontando le righe senza spazi ai bordi, ha somiglianza difflib almeno 0,8 (la soglia dello studio). I
    testi più corti dell'`old_str` non si usano. Le righe vuote (anche fatte solo di spazi) all'inizio e alla fine di `old_str` si ignorano. La
    ricerca guarda i 6 testi diversi più recenti.
- **Classe del caso**, una sola:
  - *solo whitespace:* ogni differenza è negli spazi o nelle righe vuote. Non vuol dire sempre «innocua»:
    l'indentazione fa parte del codice;
  - *solo righe:* la copia ha righe non vuote in più o in meno, ma le righe in comune sono uguali;
  - *contenuto:* almeno una coppia di righe differisce nelle parole o nei simboli.
- **Corrispondenza lessicale** di ogni riga della copia, non vuota, che non è nella finestra vera:
  - *riga vista:* una riga uguale, di almeno 12 caratteri, compare da qualche parte nei testi visti di quel file;
  - *riga non vista:* non compare;
  - *banale:* ha meno di 12 caratteri, e non si usa nella misura.
  - La corrispondenza **non prova** da dove la riga è stata copiata: può venire da un'altra zona, da una versione
    vecchia della stessa zona o essere una riga che si ripete.

## 3. Divisione

- **Sviluppo:** le prime 1.500 corse delle shard di sviluppo di SWE-Hero (0–3). Lì sono state fissate le
  definizioni.
- **Prova:** tutte le corse delle shard tenute da parte di SWE-Hero (4–13, Qwen3-Coder-480B), mai lette con questo
  metodo. Il programma richiede esplicitamente `dev` o `heldout`.
- **Parti descrittive, dati già visti con un metodo più grezzo:**
  - le traiettorie OpenHands di Qwen3-Coder 30B e 480B su SWE-bench Verified;
  - le 288 corse di Gemma della prova dal vivo.
  - Servono solo per il confronto fra modelli, non per le ipotesi.

## 4. Ipotesi e regole (parte di prova)

| | Ipotesi | Regola |
|---|---|---|
| A1 | I casi «solo whitespace» sono una minoranza | Limite superiore dell'intervallo bootstrap al 95% della quota minore di 0,5 |
| A2 | Le righe sbagliate della copia, non banali, sono per lo più righe viste altrove nei testi del file (non inventate) | Limite inferiore dell'intervallo bootstrap della quota «riga vista» maggiore di 0,5 |

- **Intervallo:** percentile a due code, bootstrap sulle corse che hanno almeno un caso (rapporto delle somme,
  pesato per eventi), 2.000 repliche, seme 20261009 (`misura.rate`).
- Le stime sono condizionate alle corse con casi. Si riportano numeratori, denominatori e repliche con
  denominatore zero scartate.

**Valori di sviluppo** (1.500 corse, 25 casi):

| Misura | Valore | Intervallo |
|---|---|---|
| Solo whitespace | 4/25 (16%) | [4%, 31%] |
| Solo righe | 5/25 (20%) | |
| Contenuto | 16/25 (64%) | |
| Righe viste | 33/49 non banali (67%) | [42%, 83%] |

Nello sviluppo A2 ha il limite inferiore sotto 0,5: l'ipotesi può fallire, e lo diremo.

## 5. Cautele

- **La finestra migliore è un'euristica.** Se la copia mescola due zone del file, il confronto con una finestra sola
  la fa sembrare «contenuto» o «solo righe».
- **La ricostruzione dei testi visti è incompleta.** Letture con percorsi relativi, comandi concatenati, grep o
  script stampano testo che non attribuiamo a un file.
  - L'esclusione delle viste vecchie usa anche tutti i risultati precedenti di qualsiasi strumento, il che riduce
    questo rischio.
  - Un controllo di sensibilità previsto (togliere i casi con un comando bash che stampa contenuto e nomina il file)
    nello sviluppo segnala tutti i 25 casi: non è informativo e si riporta solo come conteggio.
- **«Riga vista» è una corrispondenza lessicale**, non una prova di trapianto (§2).
- **La prova riguarda un solo modello** (Qwen3-Coder-480B in SWE-Hero). Il confronto con 30B e con Gemma è
  descrittivo.
- **Pochi casi:** decine per insieme, perché servono un fallimento, una copia quasi esatta e un testo visto.

## 6. Procedura

1. Revisione di Codex della bozza e di `anatomia_copie.py`.
2. Congelamento con un commit e un tag.
3. Una sola corsa sulla parte di prova, più le parti descrittive.

## 7. Revisioni di Codex: cosa è cambiato

**Revisione 1.**

| Punto | Correzione |
|---|---|
| B1: argomento mancante → prova | `dev` o `heldout` obbligatori; per Gemma serve la cartella |
| B2: ricostruzione incompleta | Letture bash solo con un percorso; risultati di una risposta visibili solo dopo la risposta; esclusione delle viste vecchie anche su ogni risultato precedente; cautela e conteggio di sensibilità (§5) |
| B3: finestre più corte | Solo finestre con esattamente lo stesso numero di righe |
| B4: A2 non misura la provenienza | A2 riformulata come corrispondenza lessicale («riga vista»), senza affermare il trapianto |
| Non bloccanti | Stime condizionate e repliche scartate dichiarate (§4); testi recenti senza duplicati presi dal più recente; «solo spazi» diventa «solo whitespace» |

**Revisione 2.**

| Punto | Correzione |
|---|---|
| B2: chiamate dello stesso messaggio | Una risposta ora è il messaggio con tutte le sue chiamate (più quelli segnati come stessa risposta). Nessuna chiamata vede i risultati delle altre della stessa risposta |
| B2: letture con più file | Una lettura bash vale solo con un percorso assoluto e nessun altro nome di file, anche relativo, e senza pipe, catene o redirezioni |
| B2: risultati precedenti | Si usano tutti i messaggi di risultato prima della risposta in corso, non solo quelli abbinati a una chiamata |
| Righe vuote ai bordi | Convenzione dichiarata (§2) |
| Rendiconto | Il programma stampa numeratori, denominatori e repliche scartate anche senza `--out` |

**Revisione 3.**

| Punto | Correzione |
|---|---|
| B2: letture con un secondo file tra virgolette, senza estensione o su più righe | La lettura pulita ora è una forma esatta dell'intero comando, su una riga, con un solo percorso assoluto e niente altro |
| Sensibilità: comandi della stessa risposta | I comandi bash della risposta in corso contano solo dopo la fine della risposta, come i risultati |
| Righe vuote fatte di spazi ai bordi | Si ignorano anch'esse |

**Revisione 4:** la lettura pulita accettava `head 10 /file` (che legge due file) e `head -n /file`. Ora accetta
solo `-n N`, `-c N` (anche con +) o `-N`, con prove su forme valide e non valide.

## Scostamenti

Nessuno.
