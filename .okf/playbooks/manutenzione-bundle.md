---
type: Playbook
title: Manutenzione del bundle
description: Tipi di concetto, regime di manutenzione di ciascuno, gate pre-commit, soglie di crescita.
resource: .okf/index.md
tags: [playbook, okf, maintenance]
generated:
  by: agent:claude-opus-5
  at: 2026-09-12T00:00:00Z
---

# Tre tipi di conoscenza, tre regimi

| tipo (`type:`) | esempi | come invecchia | chi la protegge |
|---|---|---|---|
| **Domain Logic**, **Model Reference**, **Playbook** | `domain/*`, `models/*` | il codice cambia e il testo no | `resource:`/`resources:` puntuali + gate pre-commit |
| **Invariant** | `decisions/segni-concordi.md`, `guardia-allocations.md` | qualcuno indebolisce il vincolo senza sapere il perché | `resource:` = il file dove il vincolo è **imposto** (constraint, `clean()`, signal, service) + gate |
| **Principle**, **Architecture Decision**, **Architecture** | `principles/*`, `unificazione-receivable.md`, `overview.md` | non drifta per commit: cambia per decisione esplicita | nessuna `resource:`; i principi stanno **sempre in contesto** (hook di sessione inietta `principles/index.md`); le ADR hanno `status: stable | deprecated` (i valori di §5.4) + `superseded_by:` |

Non forzare una `resource:` su ciò che non ce l'ha: un legame inventato
produce rumore nel gate e il gate viene bypassato.

# Regole per `resource:`

- File, non directory: il gate ignora le directory perché non discriminano un
  commit. Il drift check periodico invece le accetta come "ricontrolla".
- `resource:` è il file principale e si ripete come prima voce di
  `resources:` quando i file sono più d'uno (1-5).
- Per un'invariante: dove è imposta, non dove è usata.

# Cosa fa il tooling (globale, fuori dal repo)

- Hook Claude Code `SessionStart` + `SubagentStart`: inietta l'istruzione
  d'uso del bundle e i principi. I subagenti non ereditano il contesto della
  sessione: nel prompt di delega si nominano i concetti da leggere.
- `okf-gate.sh` (pre-commit, `git config okf.gate warn|block`): se il commit
  tocca un file in `resources:` senza il concetto in stage, segnala o blocca.
  `OKF_GATE=off git commit …` per i refactor meccanici.
- `okf-drift.sh`: elenca i concetti con codice più recente della loro data
  (`generated.at`), guardando il commit più recente fra **tutte** le
  `resources:` e non solo la prima. Da lanciare a mano, circa una volta al
  mese.

# Regola di commit

Il concetto si aggiorna **nello stesso commit** del codice, come i test: il
contesto per scriverlo esiste solo mentre si decide. La data del concetto
(`generated.at`) cambia solo con il contenuto (o dopo una riverifica
esplicita): toccare la data per far tacere il drift check rende il bundle
verde e bugiardo.

Il bundle è OKF v0.2 (`okf_version: "0.2"` in `index.md`): la data sta in
`generated: {by, at}` e non più in `timestamp:`. Il campo che conta è `at`,
l'unico che gate e drift check leggono. `by` c'è perché il formato lo prevede
(§5.3 ne ricava un livello di fiducia): qui lavorano solo Sandro e Claude,
quindi non discrimina niente e non va curato — `process:okf-migrate` sul
pregresso, chi scrive mette il proprio attore se gli serve. Nessuna
ri-attestazione da programmare.

Il formato conta: un concetto a elenchi (`# Invarianti`, `# Anatomia`)
accoglie una riga a costo quasi nullo; uno in prosa obbliga a riscrivere.

# Soglie di crescita

- Una directory con più di ~15 concetti si spezza per sotto-dominio, con il
  suo `index.md`. La skill OKF non lo fa da sola.
- L'index di root deve restare scorribile (~2k token): oltre, delegare ai
  sotto-index.
- `principles/index.md` va in ogni contesto: tenerlo a una riga per
  principio.

# Log

`log.md` in root, voce datata per ogni creazione/manutenzione, con il *perché*
(la trappola evitata, la regola imparata), non l'elenco delle righe cambiate.
