---
type: Domain Logic
title: Conguaglio
description: Conguaglio periodico degli addebiti e conguaglio previsionale.
resource: backend/apps/billing/management/commands/calcola_conguaglio.py
tags: [domain, conguaglio, billing]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Il conguaglio riconcilia, a fine periodo, quanto **dovuto** vs quanto già
**addebitato/incassato** all'inquilino, generando l'addebito (o l'accredito) di
differenza. Comando: `calcola_conguaglio`; storici: `genera_conguagli_storici`.

# Conguaglio reale

Somma gli addebiti effettivi del periodo (affitti + utenze reali) e li confronta
con quanto già a carico dell'inquilino. Rispetta la
[guardia allocations](/decisions/guardia-allocations.md): non tocca i Receivable
con allocazioni vive.

- **Niente doppio pro-rata**: sulle utenze reali già proratate non si riapplica
  il pro-rata in fase di conguaglio (fix noto).

# Conguaglio previsionale

Stima il conguaglio **prima** della chiusura del periodo, mostrandolo già nelle
**2 settimane precedenti** il termine, così l'inquilino vede in anticipo la cifra
attesa. Le utenze non ancora arrivate sono stimate; quelle reali sostituiscono la
stima man mano.

# Frontend

- Inquilino: `/i/conguaglio` (`InquilinoConguaglio.vue`).
- Proprietario: vista integrata nel conto economico + deep-link ai saldi fratelli.

# Vedi anche

- [Calcolo utenze](/domain/calcolo-utenze.md), [Conto economico](/domain/conto-economico.md).
