"""Rapporto HTML del giro a secco.

A terminale venti post con due messaggi ciascuno sono illeggibili. Qui si
scorrono: i lead in cima con i testi pronti da copiare, gli scartati sotto in
tabella, per controllare al volo che il filtro non stia buttando via nessuno.

File locale, non pubblicato: contiene nomi e testi di persone reali.
"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

STILE = """
:root {
  --sfondo: #fbfaf8; --carta: #fff; --bordo: #e5e0d8; --testo: #26221e;
  --tenue: #79706a; --accento: #b4541f; --ok: #2f6b45; --scarto: #94908c;
}
@media (prefers-color-scheme: dark) {
  :root {
    --sfondo: #16140f; --carta: #201d18; --bordo: #35302a; --testo: #ece7df;
    --tenue: #a09891; --accento: #e08c4e; --ok: #7cbb92; --scarto: #6d6862;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1.25rem 4rem; background: var(--sfondo); color: var(--testo);
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 52rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; letter-spacing: -.01em; }
.sommario { color: var(--tenue); font-size: .9rem; margin-bottom: 2.5rem; }
h2 {
  font-size: .8rem; text-transform: uppercase; letter-spacing: .09em;
  color: var(--tenue); margin: 3rem 0 1rem; font-weight: 600;
}
.lead {
  background: var(--carta); border: 1px solid var(--bordo); border-left: 3px solid var(--ok);
  border-radius: 10px; padding: 1.25rem 1.4rem; margin-bottom: 1.25rem;
}
.chi { font-weight: 650; font-size: 1.05rem; }
.campi { color: var(--tenue); font-size: .87rem; margin: .3rem 0 .7rem; }
.campi span::after { content: " · "; }
.campi span:last-child::after { content: ""; }
.motivo {
  font-size: .9rem; color: var(--accento); margin-bottom: .9rem;
}
.post {
  font-size: .88rem; color: var(--tenue); background: var(--sfondo);
  border-radius: 7px; padding: .7rem .85rem; margin-bottom: 1rem;
  white-space: pre-wrap; max-height: 8rem; overflow-y: auto;
}
.msg { margin-bottom: .9rem; }
.etichetta {
  font-size: .72rem; text-transform: uppercase; letter-spacing: .07em;
  color: var(--tenue); display: flex; justify-content: space-between;
  align-items: center; margin-bottom: .3rem;
}
.testo {
  font: .92rem/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--sfondo); border: 1px solid var(--bordo); border-radius: 7px;
  padding: .8rem .9rem; white-space: pre-wrap; cursor: pointer;
}
.testo:hover { border-color: var(--accento); }
button {
  font: inherit; font-size: .72rem; text-transform: uppercase; letter-spacing: .07em;
  background: none; border: 1px solid var(--bordo); border-radius: 5px;
  color: var(--tenue); padding: .15rem .55rem; cursor: pointer;
}
button:hover { border-color: var(--accento); color: var(--accento); }
a { color: var(--accento); }
table { width: 100%; border-collapse: collapse; font-size: .87rem; }
td { padding: .5rem .6rem; border-top: 1px solid var(--bordo); vertical-align: top; }
tr:first-child td { border-top: none; }
td.chi-scarto { white-space: nowrap; color: var(--scarto); font-weight: 600; }
td.perche { color: var(--tenue); }
.vuoto { color: var(--tenue); font-style: italic; }
"""

COPIA_JS = """
document.querySelectorAll('.testo').forEach(box => {
  box.addEventListener('click', () => {
    navigator.clipboard.writeText(box.textContent.trim());
    const b = box.previousElementSibling.querySelector('button');
    const prima = b.textContent;
    b.textContent = 'copiato';
    setTimeout(() => { b.textContent = prima; }, 1200);
  });
});
"""


def _e(valore) -> str:
    return html.escape(str(valore)) if valore is not None else ""


def _card(voce: dict) -> str:
    post, analisi, messaggi = voce["post"], voce["analisi"], voce["messaggi"]
    campi = []
    if analisi.zona:
        campi.append(f"<span>{_e(analisi.zona)}</span>")
    if analisi.budget_max:
        campi.append(f"<span>max {_e(analisi.budget_max)}€</span>")
    if analisi.disponibile_da:
        campi.append(f"<span>da {_e(analisi.disponibile_da)}</span>")
    campi.append(f"<span>{_e(', '.join(analisi.stanze_compatibili))}</span>")
    return f"""
    <article class="lead">
      <div class="chi">{_e(post.author_name or "anonimo")}</div>
      <div class="campi">{''.join(campi)}</div>
      <div class="motivo">{_e(analisi.motivo)}</div>
      <div class="post">{_e(post.text[:700])}</div>
      <div class="msg">
        <div class="etichetta"><span>commento sotto il post</span><button>copia</button></div>
        <div class="testo">{_e(messaggi.commento_pubblico)}</div>
      </div>
      <div class="msg">
        <div class="etichetta"><span>privato su Messenger</span><button>copia</button></div>
        <div class="testo">{_e(messaggi.privato)}</div>
      </div>
      {_link_html(post)}
    </article>"""


def _link_html(post) -> str:
    voci = []
    messenger = getattr(post, "link_messenger", None)
    if messenger:
        nome = _e(post.author_name or "questa persona")
        voci.append(f'<a href="{messenger}" target="_blank" rel="noopener">scrivi a {nome} →</a>')
    if post.permalink and not getattr(post, "permalink_e_del_profilo", False):
        voci.append(f'<a href="{_e(post.permalink)}" target="_blank" rel="noopener">apri il post →</a>')
    return " &middot; ".join(voci)


def _riga_scarto(voce: dict) -> str:
    post, analisi = voce["post"], voce["analisi"]
    return (
        f"<tr><td class='chi-scarto'>{_e(post.author_name or 'anonimo')}</td>"
        f"<td class='perche'>{_e(analisi.motivo)}</td>"
        f"<td><a href='{_e(post.permalink)}' target='_blank' rel='noopener'>post</a></td></tr>"
    )


def scrivi(percorso: str | Path, lead: list[dict], scartati: list[dict]) -> Path:
    percorso = Path(percorso).expanduser()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    quando = datetime.now().strftime("%d/%m alle %H:%M")
    totale = len(lead) + len(scartati)

    corpo_lead = (
        "".join(_card(v) for v in lead)
        if lead
        else "<p class='vuoto'>Nessun lead in questo giro.</p>"
    )
    corpo_scarti = (
        f"<table>{''.join(_riga_scarto(v) for v in scartati)}</table>"
        if scartati
        else "<p class='vuoto'>Niente di scartato.</p>"
    )

    percorso.write_text(
        f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prova del bot — {quando}</title>
<style>{STILE}</style></head>
<body><main>
  <h1>Giro a secco</h1>
  <p class="sommario">{quando} · {totale} post letti · {len(lead)} da contattare
     · nessun messaggio inviato</p>
  <h2>Da contattare</h2>
  {corpo_lead}
  <h2>Scartati ({len(scartati)})</h2>
  {corpo_scarti}
</main><script>{COPIA_JS}</script></body></html>""",
        encoding="utf-8",
    )
    return percorso
