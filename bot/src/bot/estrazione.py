"""JS di estrazione dei post dal gruppo Facebook — PUNTO FRAGILE DEL PROGETTO.

Se il bot smette di trovare post, si rompe QUI e (quasi certamente) solo qui.
Tutto il resto del codice lavora su `dict` e non conosce il DOM di Facebook.

Com'è fatto il feed (rilevato il 2026-08-27, Facebook web desktop, it_IT):

  div[role="feed"]                <- unico, contiene tutti i post
    └── div                       <- UN post per figlio diretto
          └── a[href*="/user/"]   <- autore (il primo con testo è il nome)
          └── a[href*="/posts/"]  <- permalink, QUANDO C'È (vedi trappola 4)

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

4. IL PERMALINK C'È SOLO SUI POST CHE HANNO COMMENTI. Non è una stranezza del
   rendering, è come è fatto il markup: il link a[href*="/posts/"] è il link di
   un COMMENTO, non dell'orario. Un commento dev'essere indirizzabile ("post X,
   commento Y") e quindi porta con sé l'id del post; il link dell'orario invece
   è un href relativo `?__cft__[0]=...` che Facebook risolve in JavaScript al
   click, e nel DOM non contiene l'id.

   Misurato il 27/08 su 41 post: 13 con commenti avevano tutti il permalink,
   28 senza commenti non ne aveva nessuno. Correlazione perfetta, zero
   eccezioni, e stabile fra due giri consecutivi (nessun post "si alterna").

   Conseguenze, per non riprovare quello che non funziona:
   - non dipende dal ritmo di lettura. Provati e tutti a ~40%: due letture per
     passo, pause di 2,5s fra le letture, scroll più corto del viewport, pausa
     di 7s dopo ogni scroll, ripasso del feed all'indietro.
   - non si recupera col click: sui post senza commenti, cliccare il link
     dell'orario non naviga da nessuna parte, né con element.click() né col
     mouse simulato da Playwright.
   - c'è un rovescio utile: i post senza commenti sono i più FRESCHI, cioè i
     lead migliori. Per quelli il permalink non ci sarà mai, ed è il motivo per
     cui la notifica poggia su m.me/<author_id> — che c'è sempre.

   Gli annunci Marketplace condivisi nel gruppo (a[href*="/commerce/listing/"])
   sono sempre offerte, mai richieste: si scartano prima dell'LLM.

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
    const raw = nodo.innerText || '';
    if (raw.length < 80) continue;                  // guscio virtualizzato o mezzo vuoto

    const autore = [...nodo.querySelectorAll('a[href*="/user/"]')]
      .find(a => (a.innerText || '').trim());
    const permalink = nodo.querySelector('a[href*="/posts/"]');
    const id = permalink ? permalink.href.match(/\/posts\/(\d+)/) : null;

    out.push({
      post_id: id ? id[1] : null,                   // spesso null: vedi trappola 4
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

# Sonda di salute: se torna feed=false il markup è cambiato davvero.
# `con_testo` conta i contenitori popolati, NON quelli col permalink: il
# permalink va e viene (trappola 4) e non dice niente sullo stato del feed.
DIAGNOSI_JS = r"""
JSON.stringify({
  feed: !!document.querySelector('div[role="feed"]'),
  figli: document.querySelectorAll('div[role="feed"] > div').length,
  con_testo: [...document.querySelectorAll('div[role="feed"] > div')]
               .filter(n => (n.innerText || '').length > 200).length,
  url: location.href,
})
"""
