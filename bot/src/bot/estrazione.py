"""JS di estrazione dei post dal gruppo Facebook — PUNTO FRAGILE DEL PROGETTO.

Se il bot smette di trovare post, si rompe QUI e (quasi certamente) solo qui.
Tutto il resto del codice lavora su `dict` e non conosce il DOM di Facebook.

Com'è fatto il feed (rilevato il 2026-08-27, Facebook web desktop, it_IT):

  div[role="feed"]                <- unico, contiene tutti i post
    └── div                       <- UN post per figlio diretto
          └── a[href*="/posts/"]  <- permalink, da cui si ricava il post_id
          └── a[href*="/user/"]   <- autore (il primo con testo è il nome)

Tre trappole verificate sul campo, da NON dimenticare alla prossima campagna:

1. IL FEED È VIRTUALIZZATO. Facebook svuota il contenuto dei post lontani dal
   viewport lasciando il div come guscio vuoto. Non si può scrollare fino in
   fondo e poi estrarre: si raccoglie solo l'ultima schermata. Bisogna estrarre
   A OGNI PASSO di scroll e accumulare (vedi scraper.py).

2. LO SCROLL VIA JS NON FUNZIONA. `window.scrollBy`/`scrollTo` non muovono la
   pagina in questo stato: il loop girerebbe a vuoto sempre sulla stessa
   schermata. Va usato lo scroll nativo di agent-browser (rotella vera).

3. div[role="article"] NON È IL SELETTORE GIUSTO, malgrado sia quello ovvio:
   nel markup attuale marca i COMMENTI, non i post. Un commento "cerco stanza"
   sotto un post "offro casa" farebbe classificare male il post.

`innerText` viene preso grezzo e ripulito in Python (vedi pulizia.py): meno
codice dentro il browser significa meno codice da riscrivere quando si rompe,
e la pulizia resta testabile senza aprire Chrome.
"""

# Raccoglie i post attualmente renderizzati nel DOM. Va richiamato a ogni passo
# di scroll; la deduplica per post_id è a carico del chiamante.
RACCOLTA_POST_JS = r"""
(() => {
  const out = [];
  for (const nodo of document.querySelectorAll('div[role="feed"] > div')) {
    const permalink = nodo.querySelector('a[href*="/posts/"]');
    if (!permalink) continue;                       // guscio virtualizzato
    const id = permalink.href.match(/\/posts\/(\d+)/);
    if (!id) continue;
    const raw = nodo.innerText || '';
    if (raw.length < 80) continue;                  // svuotato a metà
    const autore = [...nodo.querySelectorAll('a[href*="/user/"]')]
      .find(a => (a.innerText || '').trim());
    out.push({
      post_id: id[1],
      permalink: permalink.href.split('?')[0],      // via i parametri __cft__
      author_name: autore ? autore.innerText.trim() : null,
      author_url: autore ? autore.href.split('?')[0] : null,
      raw: raw,
    });
  }
  return out;
})()
"""

# Sonda di salute: se torna feed=false il markup è cambiato davvero.
DIAGNOSI_JS = r"""
JSON.stringify({
  feed: !!document.querySelector('div[role="feed"]'),
  figli: document.querySelectorAll('div[role="feed"] > div').length,
  con_post: [...document.querySelectorAll('div[role="feed"] > div')]
              .filter(n => n.querySelector('a[href*="/posts/"]')).length,
  url: location.href,
})
"""
