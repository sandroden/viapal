# Bot affitti — gruppo Facebook Monza/Brianza

Legge il gruppo *AFFITTI Monza e Brianza — CERCO/OFFRO*, riconosce chi cerca una
stanza compatibile con quelle libere e manda su Telegram una notifica con i due
messaggi già scritti, pronti da copiare.

**Non invia niente.** Prepara i testi; l'invio è tuo, a mano. Nel codice non
esiste nessuna funzione di invio, nemmeno disattivata — è il vincolo che tiene
il progetto fuori dai pattern antispam di Meta.

È uno strumento da campagna: dieci giorni acceso, poi in cantina per mesi. Le
scelte tecniche seguono da qui — nessun servizio, nessun monitoraggio, nessuna
sessione che debba sopravvivere.

## Come si accende

Tutto passa da `campagna.sh` (`./campagna.sh -h` per l'elenco):

```bash
cp config.toml.example ~/.viapal-bot/config.toml   # e riempi il token Telegram
chmod 600 ~/.viapal-bot/config.toml

./campagna.sh login    # apre Facebook: ti logghi a mano, poi invio
./campagna.sh prova    # un giro a secco: stampa i messaggi, non li manda
./campagna.sh loop     # il giro vero ogni 20-30 minuti, dentro un tmux
```

`login` chiude la finestra da solo quando hai finito, perché Chrome tiene un
lock sulla directory del profilo e il loop non partirebbe.
`./campagna.sh stato` dice se la sessione regge ancora, a freddo, esattamente
come farà il loop.

Deve girare **da casa**. La sessione Facebook esce abitualmente da un IP
residenziale della zona: se comincia a fare richieste da un datacenter scatta un
checkpoint e si finisce a rifare login a ogni giro.

## Le stanze

Stanno nel TOML, che viene **riletto a ogni giro**. Quando una si affitta si
mette `libera = false` e si salva: nessun riavvio. Se sono tutte occupate il bot
non notifica.

Prezzo e spese condominiali sono campi separati, e `nota_utenze` dice cosa resta
fuori dal totale. Serve a impedire al composer di scrivere "tutto incluso", che
sarebbe un preventivo falso.

## Le tre trappole trovate sul campo

Verificate il 2026-08-27, con agent-browser 0.27.0. Sono documentate anche in
`src/bot/estrazione.py`, che è l'unico file da toccare quando si rompe.

1. **`div[role="article"]` non è il selettore giusto**, malgrado sia quello
   ovvio: nel markup attuale marca i *commenti*, non i post. Il contenitore
   buono è `div[role="feed"] > div`.
2. **Il feed è virtualizzato**: i post lontani dal viewport vengono svuotati.
   Non si può scrollare fino in fondo e poi estrarre — si raccoglie solo
   l'ultima schermata. Si estrae a ogni passo di scroll e si accumula.
3. **Lo scroll via JavaScript non funziona**: `window.scrollBy` non muove il
   feed. Serve lo scroll nativo di agent-browser (rotella vera).

E due sul browser:

- **Chrome tiene un lock sulla directory del profilo.** La finestra headed del
  login va chiusa prima di far girare il loop, altrimenti "profile in use".
- **In headless la User-Agent dice `HeadlessChrome`.** Su un profilo che si è
  loggato headed è un cambio di dispositivo a sessione già stabilita. Il campo
  `user_agent` nel TOML la fissa a quella headed.

## Checklist di riattivazione (fra mesi)

1. Aggiorna `[[stanze]]` con quelle davvero libere, prezzi e spese compresi
2. `./campagna.sh login`: dai per scontato che la sessione sia scaduta
3. `./campagna.sh azzera` (cancella il database della campagna precedente)
4. Verifica che l'estrazione torni post non vuoti — **è il punto che si rompe
   per primo**: `./campagna.sh prova`
   Se non trova niente, il problema è quasi certamente in `estrazione.py`, e
   probabilmente è cambiato il selettore del contenitore. Se sistemarlo costa
   più di un'ora, valuta se conviene ancora rispetto al lavoro a mano.
5. Ricontrolla la UA headless: `agent-browser --profile ~/.viapal-bot/fb-profile
   eval 'navigator.userAgent'`, e riallinea `user_agent` nel TOML
6. Un giro a secco per controllare che la classificazione sia ancora sensata

`agent-browser` è giovane e si muove in fretta: fra una campagna e l'altra è
probabile che il CLI sia cambiato. Questa versione gira su **0.27.0**.

## Struttura

| file | cosa fa |
|---|---|
| `estrazione.py` | il JS che legge il DOM di Facebook — **il punto fragile** |
| `browser.py` | wrapper su agent-browser, sola lettura |
| `scraper.py` | scroll + accumulo, si ferma sui post già visti |
| `pulizia.py` | ripulisce l'innerText, taglia i commenti |
| `classifier.py` | una chiamata per post: cerca/offre, tipo, budget, match |
| `composer.py` | i due messaggi, con il divieto di inventare dettagli |
| `notifier.py` | Telegram, testi in blocchi copiabili con un tap |
| `storage.py` | SQLite di campagna: dedup su post e su autore |

## Test

```bash
uv run pytest tests -q                              # senza browser né rete
uv run python tests/prova_su_fixture.py --componi   # su post veri salvati
```
