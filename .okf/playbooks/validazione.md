---
type: Playbook
title: Validazione (test + agent-browser)
description: I due livelli di verifica obbligatori per ogni feature.
tags: [playbook, testing, validation]
timestamp: 2026-07-08T00:00:00Z
---

# Regola

Ogni feature si valida a **due livelli** (PLAN.md § "Validazione obbligatoria"):

1. **Test pytest backend**:
   ```bash
   just test-backend    # oppure: just test
   ```
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
