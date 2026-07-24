---
type: Feature
title: Proprietà a unità intera
description: Property.tipo_gestione "unita_intera" reinterpreta Room come unità locata con un'unica Room implicita "Appartamento".
resource: backend/apps/properties/
tags: [feature, properties, domain, multiproprieta]
timestamp: 2026-07-24T00:00:00Z
---

# Overview

Alcune proprietà non si affittano a stanze ma **per intero a un solo inquilino**
(caso di collaudo: "l'appartamento della moglie", cfr. il [piano
multiproprietà](../../docs/piano-multiproprieta.md) §5.3). Per gestirle senza
duplicare la catena contabile, `Property` porta il campo
**`tipo_gestione`** (`TextChoices`, verbose "tipo di gestione"):

- **`stanze`** (default) — comportamento storico ad affitto per camere.
- **`unita_intera`** — l'immobile è locato come unità unica.

Migrazione `0019_property_tipo_gestione`. **Fallback ovunque**: `tipo_gestione`
assente ⇒ comportamento "a stanze" (nessuna regressione sulla produzione a una
sola property).

# Perché non una FK dedicata

Scelta deliberata (strada A): **riusare `Room` reinterpretandola come "unità
locata"** invece di introdurre un modello/relazione separata per l'unità intera.
Una FK diretta `Property → inquilino` avrebbe biforcato ogni calcolo
(Receivable, utenze, conguagli, saldi) in due percorsi. Reinterpretando `Room`,
la catena `Receivable → RoomAssignment → Room → Property` resta **una sola** e
identica per entrambi i tipi.

# Room implicita "Appartamento"

Per una property `unita_intera` il backend crea **automaticamente UNA sola** Room
implicita di nome "Appartamento" (signal `post_save` su `Property` in
`properties/signals.py`, `genera_room_implicita`).

Vincoli (`Room.clean` + validazione API):

- **max 1 Room** su una property `unita_intera`;
- il **cambio tipo → `unita_intera`** è vietato se esiste più di una stanza;
- il cambio **`unita_intera` → `stanze`** è sempre libero.

# Prima assegnazione

Nell'action **prima-assegnazione** il campo `room` del payload è **opzionale**:
su `unita_intera`, se assente, il backend risolve (o crea) l'unità implicita; su
`stanze` l'assenza di `room` è un errore (400). Vedi [Prima
assegnazione](generazione-affitti.md).

# Invariante di dominio

**Un'unità intera = un solo pagatore intestatario.** Niente co-intestatari
(fuori scope). La ripartizione utenze pro-rata degrada correttamente al pagatore
unico (quota 100%): nessun ramo speciale nel [calcolo utenze](calcolo-utenze.md).

# Esposizione API

`tipo_gestione` è esposto in: `PropertySerializer`, `/api/auth/user/`
(`properties[]`), home inquilino (dentro `stanza_corrente`) e
`PublicGallerySerializer` (`/g/<slug>`). Sul frontend guida la **terminologia**
(getter nello store `properties`: Unità/Appartamento/Assegna appartamento/
Occupazione…), il dialog di assegnazione (senza select stanza) e la [galleria
pubblica](galleria-pubblica.md) (per `unita_intera` nasconde "Libera dal" e la
disponibilità, hero fallback "Appartamento in affitto").

# Vedi anche

- [properties](/models/properties.md) — campo `tipo_gestione`, Room implicita.
- [Modello dati](/architecture/modello-dati.md) — Room = unità locata.
- [Generazione affitti](/domain/generazione-affitti.md) — prima-assegnazione.
- [Calcolo utenze](/domain/calcolo-utenze.md) — degradazione al pagatore unico.
