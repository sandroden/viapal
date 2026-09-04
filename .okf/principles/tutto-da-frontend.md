---
type: Principle
title: Tutto utilizzabile dal frontend
description: Ogni operazione che serve a un proprietario o a un inquilino si compie dalla PWA; l'admin Django è un fallback per il superuser, non un'interfaccia utente.
tags: [principle, frontend, admin]
timestamp: 2026-09-05T00:00:00Z
---

# Principio

Chi usa viapal è un proprietario o un inquilino, e usa la PWA (`/p/`, `/i/`).
Una funzionalità esiste quando è raggiungibile da lì: endpoint DRF **e**
pagina o dialog. L'admin Django serve al superuser per diagnosi, dati di
seed e correzioni una tantum; non è il posto dove una funzionalità "vive
intanto", perché poi ci resta.

# Come riconoscere una violazione

Fermarsi se si sta per:

- aggiungere un'**azione admin** (`actions = [...]`, bottone in change_form)
  che un proprietario dovrebbe poter compiere da solo;
- rendere un campo **editabile solo in admin** (o solo via management command)
  quando la sua modifica è un'operazione ordinaria;
- chiudere una feature con "per ora si fa dall'admin".

In ciascun caso manca una delle due metà: l'endpoint o la pagina. Se la metà
mancante non si può fare ora, il commit lo dice esplicitamente e la cosa va
nel `PLAN.md`, non nel silenzio.

# Eccezioni legittime

- Operazioni di **migrazione dati** e ricette di produzione (management
  command lanciati una volta: `carica_modelli_documenti`,
  `sana_incassi_senza_incassante`, import storici).
- **Diagnosi** che riguardano il superuser e non un ruolo dell'app.
- Il cruscotto admin-tools, che è uno strumento del superuser per costruzione.

# Perché

Il progetto è nato con molte operazioni in admin (jmb.jadmin, tabs, modal) e
le ha portate una per una sul frontend — inviti, conti bancari, quote
condominio, anagrafica owner, correzione assegnazione. Ogni volta il costo è
stato più alto che farlo subito, perché nel frattempo l'admin aveva accumulato
comportamento (validazioni, default) che il frontend doveva reimplementare.
