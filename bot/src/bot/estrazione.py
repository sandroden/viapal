"""JS di estrazione dei post dal gruppo Facebook — PUNTO FRAGILE DEL PROGETTO.

Se il bot smette di trovare post, si rompe QUI e (quasi certamente) solo qui.
Tutto il resto del codice lavora su `dict` e non conosce il DOM di Facebook.

Com'è fatto il feed (rilevato il 2026-08-27, Facebook web desktop, it_IT):

  div[role="feed"]                <- unico, contiene tutti i post
    └── div                       <- UN post per figlio diretto
          └── a[href*="/user/"]   <- autore (il primo con testo è il nome)
          └── a[href^="?"]        <- orario, con l'href MASCHERATO (trappola 4)
          └── a[href*="/posts/"]  <- permalink: orario smascherato o link commento

Quattro trappole verificate sul campo, da NON dimenticare alla prossima campagna:

1. IL FEED È VIRTUALIZZATO. Facebook svuota il contenuto dei post lontani dal
   viewport lasciando il div come guscio vuoto. Non si può scrollare fino in
   fondo e poi estrarre: si raccoglie solo l'ultima schermata. Bisogna estrarre
   A OGNI PASSO di scroll e accumulare (vedi scraper.py).

2. LO SCROLL VIA JS NON FUNZIONA. `window.scrollBy`/`scrollTo` non muovono la
   pagina in questo stato: il loop girerebbe a vuoto sempre sulla stessa
   schermata. Va usato lo scroll nativo di agent-browser (rotella vera).
   Della stessa famiglia: lo scrollIntoView di Playwright (`hover <sel>`,
   `scrollintoview <sel>`) dichiara successo ma NON porta l'elemento nel
   viewport — il mouse finisce su un altro punto della pagina.

3. div[role="article"] NON È IL SELETTORE GIUSTO, malgrado sia quello ovvio:
   nel markup attuale marca i COMMENTI, non i post. Un commento "cerco stanza"
   sotto un post "offro casa" farebbe classificare male il post.

4. IL PERMALINK NASCE MASCHERATO, E SI SMASCHERA COL MOUSE. L'href dell'orario
   è `?__cft__[0]=…` (token opaco, l'id del post NON c'è) e Facebook lo
   riscrive pieno — `/groups/<gid>/posts/<id>/?__cft__…` — solo quando il
   mouse ci passa sopra con un evento TRUSTED. È il motivo per cui "da
   browser funziona": il mouse dell'utente smaschera senza che se ne accorga.
   Validato il 27/08 su feed caricato da zero: sola discesa 70%, discesa più
   ripasso in risalita 11/11 post col permalink (8 via hover, 3 via commento).

   Le regole del gioco, misurate una a una:
   - servono eventi VERI (mouse CDP): `dispatchEvent` di mouseover/mouseenter/
     pointerover/focus non fa nulla, Facebook controlla `isTrusted`.
   - lo smascheramento PERSISTE sul nodo anche quando il mouse se ne va, ma la
     virtualizzazione ricrea i nodi evicted RIMASCHERATI: lo sweep va rifatto
     a ogni passo, la raccolta accumula (scraper.py).
   - smascherato, l'orario è il primo `a[href*="/posts/"]` del post (viene
     prima dei commenti nel DOM): RACCOLTA_POST_JS lo trova da sé.
   - i post CON commenti hanno comunque il permalink gratis: il link di un
     commento porta l'id del post (`…/posts/<id>/?comment_id=…`).
   - nei post con foto compare `set=pcb.<id>`: per i post di persone coincide
     con l'id del post, ma per pagine/cross-post punta al post ORIGINALE della
     pagina (2 divergenti su 3 misurati). NON usarlo come fallback: un link
     sbagliato è peggio di uno assente.
   - niente React fiber: Comet non attacca `__reactFiber$`/`__reactProps$` ai
     nodi (solo `__reactHandles$`/`__reactListeners$`, sterili). Vicolo cieco.
   - cliccare l'orario mascherato non naviga (né element.click() né mouse
     simulato): non insistere per quella strada, e comunque non serve.

   Gli annunci Marketplace condivisi nel gruppo (a[href*="/commerce/listing/"])
   sono sempre offerte, mai richieste: si scartano prima dell'LLM.

`innerText` viene preso grezzo e ripulito in Python (vedi pulizia.py): meno
codice dentro il browser significa meno codice da riscrivere quando si rompe,
e la pulizia resta testabile senza aprire Chrome.
"""

# Raccoglie i post attualmente renderizzati nel DOM. Va richiamato a ogni passo
# di scroll; la deduplica per impronta è a carico del chiamante.
RACCOLTA_POST_JS = r"""
(() => {
  const out = [];
  for (const nodo of document.querySelectorAll('div[role="feed"] > div')) {
    const raw = nodo.innerText || '';
    if (raw.length < 80) continue;                  // guscio virtualizzato o mezzo vuoto

    const autore = [...nodo.querySelectorAll('a[href*="/user/"]')]
      .find(a => (a.innerText || '').trim());
    const permalink = nodo.querySelector('a[href*="/posts/"]');
    const id = permalink ? permalink.href.match(/\/posts\/(\d+)/) : null;

    out.push({
      post_id: id ? id[1] : null,                   // null finché l'orario è mascherato
      permalink: permalink ? permalink.href.split('?')[0] : null,
      author_name: autore ? autore.innerText.trim() : null,
      author_url: autore ? autore.href.split('?')[0] : null,
      // l'id numerico apre la chat Messenger diretta: m.me/<id> (vedi notifier)
      author_id: autore ? (autore.href.match(/\/user\/(\d+)/) || [])[1] ?? null : null,
      // gli annunci Marketplace sono sempre offerte: si scartano prima dell'LLM
      marketplace: !!nodo.querySelector('a[href*="/commerce/listing/"]'),
      raw: raw,
    });
  }
  return out;
})()
"""

# Coordinate (nel viewport) degli orari ancora mascherati: il chiamante ci
# porta il mouse sopra (Browser.muovi_mouse) e Facebook riempie l'href.
# Al più due anchor per post: il primo `a[href^="?"]` è quasi sempre l'orario,
# il secondo copre gli ordinamenti strani; se sfuggono, riprovano il passo
# dopo o il ripasso.
ORARI_MASCHERATI_JS = r"""
(() => {
  const out = [];
  for (const nodo of document.querySelectorAll('div[role="feed"] > div')) {
    if ((nodo.innerText || '').length < 80) continue;
    if (nodo.querySelector('a[href*="/posts/"]')) continue;   // già leggibile
    let presi = 0;
    for (const a of nodo.querySelectorAll('a[href^="?"]')) {
      const r = a.getBoundingClientRect();
      const x = Math.round(r.x + r.width / 2), y = Math.round(r.y + r.height / 2);
      // sotto ~100px c'è l'header sticky di Facebook: il mouse colpirebbe quello
      if (y < 100 || y > window.innerHeight - 15 || r.width < 4) continue;
      out.push({x: x, y: y});
      if (++presi >= 2) break;
    }
  }
  return out;
})()
"""

# Sonda di salute: se torna feed=false il markup è cambiato davvero.
# `con_testo` conta i contenitori popolati, NON quelli col permalink: il
# permalink arriva con lo sweep del mouse e non dice niente sullo stato del feed.
DIAGNOSI_JS = r"""
JSON.stringify({
  feed: !!document.querySelector('div[role="feed"]'),
  figli: document.querySelectorAll('div[role="feed"] > div').length,
  con_testo: [...document.querySelectorAll('div[role="feed"] > div')]
               .filter(n => (n.innerText || '').length > 200).length,
  url: location.href,
})
"""
