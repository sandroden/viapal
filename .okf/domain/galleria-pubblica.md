---
type: Feature
title: Galleria pubblica (annuncio affitto)
description: Pagina pubblica /g/<slug> con foto per stanza/spazi comuni, editabile in-place dal proprietario.
resource: backend/apps/properties/
tags: [feature, public, gallery, frontend]
timestamp: 2026-07-14T00:00:00Z
---

# Overview

Pagina **pubblica senza login** che presenta la casa/stanze in affitto come annuncio
(hero, planimetria, sezioni stanza con foto, posizione). Unica area pubblica dell'app.
Editabile **in-place** dal proprietario loggato (stessa pagina, toggle "Modifica").
Sviluppata sul branch `galleria-pubblica` staccato da `main` (indipendente dalla
multiproprietà non ancora validata); legata a `Property`, compatibile col merge futuro.

# Modello dati

Estende [properties](/models/properties.md):

- **`Property`**: `slug` (URL pubblico), `pubblica` (toggle), immagini singleton
  `foto_hero`/`foto_planimetria`/`foto_mappa`, `testi_pubblici` (JSONField: hero, `facts`
  mq/camere/bagni/letti, `posizione` indirizzo/mezzi/parcheggio/regole). Slug auto in
  `save()`; migration 0015 popola gli esistenti.
- **`Room`**: campi d'annuncio espliciti `colore`, `descrizione`, `disponibile`,
  `libera_dal`, `prezzo_mensile`, `pubblica` — **indipendenti** dalle `RoomAssignment`
  contabili (si annuncia una stanza a prescindere dal contratto in corso). `disponibile=False`
  → badge "Non disponibile" e **niente foto** (regola di design).
- **`GalleryImage`**: foto multiple, `property` FK + `room` FK **nullable** (`room=None` =
  spazio comune). Upload in `media/galleria/<slug>/`.

# API

- **Pubblica**: `GET /api/v1/public/galleria/<slug>/` — **AllowAny** (unica del progetto),
  `PublicGallerySerializer` dedicato, 404 se `pubblica=False`. Espone solo campi pubblici.
- **Scrittura** (proprietari): `PATCH` su `properties`/`rooms` (testi, campi, immagini
  singleton), `GalleryImageViewSet` CRUD foto (MultiPartParser). Clear di un'immagine
  singleton = PATCH con `null` (non `''` → 400).

# Frontend

Route `/g/:slug` `meta.public`, `GalleriaPubblica.vue` (sola lettura per anonimi). Edit-mode
per proprietario: `ImageSlot.vue` (upload file/drag/**paste Ctrl-V** via listener `document`
+ hover), `EditableText.vue` (`q-popup-edit`, **no contenteditable**). Store `galleria.ts`.

# Note operative

- `/media` è servito pubblicamente (dev `static()`, prod Traefik→Django) — le foto galleria
  stanno in sottocartella dedicata `galleria/`. (Nota preesistente: anche i documenti privati
  sotto `/media` sono raggiungibili — fuori scope qui.)
- Per pubblicare: deploy + `Property.pubblica=True` via admin.

# Vedi anche

- [properties](/models/properties.md), [Auth e ruoli](/architecture/auth-e-ruoli.md),
  [PWA](/architecture/pwa.md) (route SPA non in denylist SW).
