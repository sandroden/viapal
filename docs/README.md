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
- [piano-link-lettura.md](piano-link-lettura.md) — pagina pubblica a token per
  far leggere i documenti a un inquilino in arrivo, senza account e senza i
  dati di chi ha firmato prima. Approvato il 2026-08-26, da implementare.
