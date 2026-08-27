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

## Come decide

Il messaggio non fa un preventivo: fa venire voglia di guardare. I prezzi stanno
nell'annuncio, scritti chiari — il link li porta, e chi clicca li legge *dopo*
aver visto com'è fatta la casa. Non si nasconde niente, si mette solo la foto
prima del listino.

Il materiale con cui incuriosire sta in `[casa]` nel TOML, ed è l'unico che il
composer ha il permesso di usare: se una cosa non è scritta lì, non la può dire.
Sono i fatti veri presi dall'annuncio Facebook e dai testi della galleria.

Il prezzo però va detto subito in due casi: quando lo chiede lui nel post, e
quando la stanza costa più del budget che ha indicato. Farglielo scoprire
cliccando sarebbe una furbata.

Sul budget il filtro è morbido di proposito: chi scrive 450€ spesso non sa ancora
quanto costi Monza, e alza il tiro quando vede la casa. Si scrive lo stesso, con
la stanza più economica e dicendo di quanto siamo sopra. Scarta solo chi dichiara
il budget come limite rigido ("massimo", "non posso superare").

Sulla zona il criterio non è la distanza ma il **prezzo di mercato**: Monza costa
più dei comuni intorno, e chi cerca dove si paga meno ha in testa cifre più basse.
È l'unico punto in cui il dubbio non premia il lead: "Lesmo o vicinanze ben
collegate" viene scartato, perché chi scrive così ragiona sui prezzi di Lesmo.
Serve che Monza o un comune della lista sia nominato davvero.

Le stanze sono a uso singolo, quindi chi cerca per due — marito e moglie,
fidanzati, due amiche che vogliono stare insieme — viene scartato. La soglia non
è scritta a mano: deriva dal `tipo` delle stanze libere nel TOML, così il giorno
che ne compare una doppia la regola si allarga da sé. Attenzione alla differenza
fra "cerco per mio figlio" (una persona, va tenuto) e "per me e mio figlio" (due,
salvo che vogliano due stanze separate — che noi possiamo dare).

Chi dichiara di avere un animale invece non riceve niente: in casa non sono
ammessi, e scrivergli sarebbe tempo perso per tutti e due.

## Due modi di farlo girare

**Con Claude Code** (`/loop 25m /affitti`) — la classificazione e la scrittura
le fa Claude dentro la sessione, quindi rientrano nell'abbonamento e non costano
API. Il Python fa solo scraping, dedup e notifiche:

```bash
uv run python -m bot.main --estrai   /tmp/affitti-post.json   # post nuovi in JSON
uv run python -m bot.main --notifica /tmp/affitti-lead.json   # notifiche + registrazione
```

Lo slash command sta in `bot/comandi/affitti.md` e si attiva con un symlink
(`.claude/` è ignorato da git, quindi il comando è versionato qui e collegato lì):

```bash
ln -sf ../../bot/comandi/affitti.md .claude/commands/affitti.md
```

Non ripete le regole: dice di leggerle da `classifier.py` e `composer.py`, così
le due modalità non possono divergere.

**Da solo** (`./campagna.sh loop`) — chiama l'API e non ha bisogno di nessuno
davanti. Costa (vedi sotto), ma gira anche di notte e mentre fai altro.

## Quanto costa (solo per la modalità autonoma)

Serve credito sull'**API** di Anthropic: l'abbonamento Claude (Pro o Max) copre
claude.ai e Claude Code, cioè l'uso interattivo, e non vale qui. Sono due prodotti
con billing separato, e non c'è un ponte fra i due.

Con i numeri di un giro reale (50 post letti, 6 lead), tenendo la
classificazione su Haiku e la scrittura su Opus:

| | |
|---|---|
| primo giro della campagna | ~$0.20 |
| giro successivo (solo post nuovi) | ~$0.03 |
| giornata di loop (15 ore, ogni 25 min) | ~$1 |
| campagna di 10 giorni | **~$10** |

Su Opus per tutto sarebbe circa quattro volte tanto, senza migliorare le
notifiche: quello che cambia davvero è il modello del `composer`, e quello è
già su Opus. Se le classificazioni cominciano a sbagliare, `classifier` nel
TOML si alza a `claude-sonnet-5` e si ricontrolla con `./campagna.sh prova`.

## I link della notifica

Ogni lead porta due link, in quest'ordine:

1. **scrivi a <nome>** → `m.me/<id autore>`, che apre la conversazione Messenger.
   È il primo perché è lì che va incollato il messaggio privato.
2. **apri il post** → solo quando abbiamo il permalink vero.

Il profilo dentro al gruppo (`/groups/<gid>/user/<uid>/`) **non** si usa come
link: l'app mobile non lo gestisce e ricade sulla pagina del gruppo. Era il
motivo per cui certi "apri il post" finivano nel posto sbagliato, e più sul
telefono che sul desktop.

Il permalink si ottiene per **circa il 40% dei post** e non è un difetto
rimediabile da qui: Facebook lo espone solo sui post che idrata del tutto
mentre si scrolla, e la quota non cambia né leggendo due volte per passo né
allungando le pause (misurato). L'`author_id`, invece, c'è sempre — per questo
il flusso poggia su Messenger e non sul post.

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
