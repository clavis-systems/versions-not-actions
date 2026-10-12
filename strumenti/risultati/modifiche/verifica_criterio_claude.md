# Criterio delle mie etichette (Claude) per la verifica a campione

Riferimento: PREMESSA_MODIFICHE §7.4, campione `verifica_campione.json`, etichette in `verifica_etichette_claude.jsonl`.

Scritto l'11/10/2026.
- Le regole generali e quelle delle categorie 1–2 le avevo già applicate ai casi 1–40 senza scriverle: qui le metto
  come le ho usate.
- Le regole delle categorie 3–6 le scrivo ora, prima di etichettare i casi 41–120. Dei casi 41–46 avevo già visto
  una vista compatta.

**Cosa guardo.**
- Solo il campione: la chiamata, il risultato e i messaggi vicini, tagliati a 400 caratteri.
- Non apro i log completi.
- Non apro le etichette di Codex prima di aver finito le mie.

## Regola generale

- **corretto:** la finestra mostra i fatti che definiscono la categoria.
- **sbagliato:** la finestra contraddice l'etichetta.
- **incerto:** i fatti decisivi non si vedono, perché sono fuori dalla finestra o oltre il taglio dei 400 caratteri.

## Per categoria

1. **noop.** Il messaggio d'errore dice che il testo nuovo è uguale al vecchio. Basta il messaggio.
2. **stale (vista vecchia).**
   - Serve vedere nella finestra che il file è stato cambiato dopo che l'agente ne aveva visto il testo, e che il
     testo cercato è quello di prima.
   - Se il cambiamento non si vede, o riguarda un percorso scritto in modo diverso: incerto.
3. **never_seen (non osservato nel log).** L'affermazione è negativa: il testo cercato non c'è in nessun testo del
   file visto prima. La finestra può confermarla solo se mostra tutti i testi del file che potevano contenerlo.
   - **corretto:**
     - la storia del file che conta è dentro la finestra (per esempio il file è nato nella finestra) e il testo
       cercato non c'è;
     - oppure la finestra mostra che il testo cercato mescola righe che non sono mai state insieme (per esempio la
       versione vecchia e quella nuova di un pezzo cambiato nella finestra).
   - **sbagliato:** la finestra mostra il testo cercato, intero per quanto si vede, in un'uscita precedente. Vale
     anche per un'uscita che il rilevatore non conta: grep, git diff, cat con un percorso relativo, un percorso
     scritto in modo diverso.
   - **incerto:** il testo cercato potrebbe essere una versione vista prima della finestra, e nulla di visibile lo
     esclude.
   - Il confronto meccanico (esatto, e con gli spazi normalizzati) lo fa il programma: io controllo solo che la
     finestra non lo contraddica.
4. **multiple.** Il messaggio d'errore dice che il testo compare più volte.
5. **known_bad_retry (versione propria già fallita).** La finestra deve mostrare due fatti:
   - (a) il blocco scritto ora è una versione scritta prima dall'agente e poi tolta;
   - (b) mentre quel blocco era presente, un comando di test è fallito con la riga indicata (`known_bad`).
   - Incerto se uno dei due fatti non si vede.
   - Sbagliato se la finestra li contraddice: per esempio il test era passato, o il blocco non è lo stesso.
6. **circle (cerchio).** Come la 5. In più, anche la versione che la modifica toglie aveva fallito un test
   (`replaced_bad`).
