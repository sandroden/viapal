# Viapal · documentazione

Documentazione tecnica e slide di progetto.

## Slide

Le slide sono scritte in [marp](https://marp.app/) (Markdown + frontmatter).

### Build PDF

```bash
bunx @marp-team/marp-cli docs/contabilita-fratelli.md --pdf
```

### Anteprima HTML in watch

```bash
bunx @marp-team/marp-cli --watch docs/contabilita-fratelli.md --html
```

## Indice

- [contabilita-fratelli.md](contabilita-fratelli.md) — modello dati e flussi
  della contabilità tra i tre fratelli proprietari (livelli A/B, settlement,
  BT inter-owner, saldi live).
- [operazioni-inquilini.md](operazioni-inquilini.md) — funzionalità lato
  inquilino (generazione Receivable affitto/utenze, riconciliazione, UI),
  punti d'ingresso (admin, action, CLI) e operazioni di manutenzione
  ordinaria (con esempi cron).
