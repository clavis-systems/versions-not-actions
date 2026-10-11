**NON PRONTA.** Revisione statica del materiale fornito: dati, ricalcolo dello sviluppo e 38 test dichiarati non sono verificati.

- **B1 — risolto in parte:** provenienza conservata, ma sovrapposizioni parziali possono ancora produrre falsa presenza certa; la cronologia usa indici dei messaggi.
- **B2 — risolto in parte:** abbinamento ed esiti sconosciuti corretti; identificativi duplicati possono ancora sovrascrivere i risultati abbinati.
- **B3 — risolto in parte:** nomi interi corretti; restano perdite del `thought` comune e allocazioni errate dei token nelle risposte con più chiamate.
- **B4 — risolto in parte:** denominatore e soglia coerenti; mancano conteggi separati delle versioni proprie escluse per presenza incerta.
- **B5 — risolto:** Clopper–Pearson per esecuzione elimina il falso sostegno automatico con zero menzioni.
- **B6 — risolto:** pareggi, denominatori zero, intervalli assenti e valori JSON non finiti sono gestiti.
- **B7 — risolto in parte:** letture iniziali, fallimenti e costi migliorati; invalidazioni incomplete e numeri di riga bash possono falsare le classificazioni.
- **B8 — risolto:** eliminata la pretesa dei limiti inferiori; selezione e filtro incerto dichiarati.
- **B9 — risolto in parte:** controlli obbligatori aggiunti, ma non garantiscono abbinamenti univoci; identificativi estranei diventano ancora `unresolved`.
- **B10 — risolto in parte:** avvio registrato prima delle misure, ma dopo la lettura integrale degli input per hashing; un’interruzione lì non lascia traccia.
- **B11 — risolto in parte:** specifica ampliata; restano incompleti ordinamento delle esecuzioni, gestione della storia precedente e alcune regole descrittive.
- **N1 — risolto per H2:** ricampionamento appaiato; nel caricatore OpenHands `task=id`, con controllo degli identificativi unici.
- **N2 — risolto:** mediana usuale e casi senza modifica successiva conteggiati.
- **N3 — risolto in parte:** §4 corregge l’interpretazione, ma §6 conserva «limite superiore della dimenticanza dichiarata».
- **N4 — non risolto:** la cronologia degli accessi resta non verificabile; questo, da solo, non blocca.

Ulteriori problemi concreti della versione corretta; senza il vecchio codice completo non posso attribuirne con certezza l’introduzione alle correzioni:

1. **Falso `known_bad`.** Nel file `abcdefghXYZ`, il blocco registrato `abcdefgh` resta “presente” dopo `fghXYZ → ZZZABC`: il controllo non rileva questa sovrapposizione. Un test fallito durante l’assenza del blocco può poi essergli attribuito.

2. **Invalidazioni saltate.** In `edit_failures()`, una `str_replace` sconosciuta entra nel ramo precedente a quello che aggiorna `modified`. Anche una scrittura bash non identificabile non invalida nulla.

3. **Cronologia multicall e memoria storica.** Scrittura, test e rimozione nella stessa risposta condividono l’indice: il test viene escluso. Inoltre `life[p][old]` sovrascrive la vita precedente, facendo perdere fallimenti storici dopo una presenza senza test; questa restrizione va dichiarata o corretta.

4. **Contesto e token.** Con due chiamate nello stesso messaggio SWE-Hero, una fallita, e 100 token, il codice attribuisce **100 anziché 50** al fallimento. La traduzione OpenHands può inoltre perdere il `thought` di una `think` comune alle modifiche successive.

5. **H4 non coincide con l’enunciato.** `names_in()` comprende i test: `test_a AssertionError` e `test_b AssertionError` diventano “due errori diversi”. Una sola menzione di `AssertionError` soddisfa entrambi.

6. **Altre discrepanze con la premessa.** Una scrittura bash sullo stesso percorso dà `project_changed=False`, contro §3; le letture bash numerate non vengono ripulite, contro §9. `check_edit()` ignora inoltre una raw `str_replace` associata a un’azione diversa da `edit`.

**Verdetto: NON PRONTA.** Bloccano l’affidabilità della presenza e delle viste, il contesto/token multicall, la validazione di abbinamenti e identificativi, l’allineamento di H4 e delle definizioni, e la registrazione preventiva dell’avvio. Dopo le correzioni serve un nuovo ricalcolo dello sviluppo con impronte aggiornate.