---
type: Playbook
title: Validazione (test + agent-browser)
description: I due livelli di verifica obbligatori per ogni feature.
resource: justfile
tags: [playbook, testing, validation]
timestamp: 2026-09-05T00:00:00Z
---

# Regola

Ogni feature si valida a **due livelli** (PLAN.md § "Validazione obbligatoria"):

1. **Test pytest backend** (`just test-backend *args` → `cd backend && ENV=dev uv run pytest`):
   ```bash
   just test-backend                      # tutto (alias: just test)
   just test-backend apps/billing -k utenze
   ```
   Test in parallelo da più sessioni: ogni sessione usa un DB di test proprio
   (`VIAPAL_DB_NAME`), altrimenti pytest si pesta i piedi sul database.
   Lint: `just lint` (ruff + eslint), `just type-check` (vue-tsc).
2. **Verifica funzionale via agent-browser** con screenshot in
   `tests/screenshots/<feature>/`. Gli screenshot sono il modo principale per
   vedere visivamente lo stato del lavoro.

# Preferenze

- Validare il web con la **grafica** (screenshot), non solo con i test.
- Usare **agent-browser** (preferito) salvo servano feature non offerte
  (es. autenticazioni 2FA → allora Chrome).
- Per la validazione autonoma: utente QA proprietario temporaneo + dev server.

# Vedi anche

- [Dev setup](/playbooks/dev-setup.md).
