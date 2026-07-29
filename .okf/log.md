# Update Log

## 2026-07-29
* **Maintain**: `domain/galleria-pubblica.md` — ridimensionamento client-side in `ImageSlot` (`utils/image.ts`, WebP ≤1920px, fallback su file non decodificabili) e dialog "Scarica foto" (selezione miniature; una foto = file singolo, più foto = ZIP store-only generato da `utils/zip.ts`).

## 2026-07-24
* **Creation**: `domain/unita-intera.md` — proprietà a unità intera (`Property.tipo_gestione` `stanze`/`unita_intera`, Room implicita "Appartamento", vincolo max-1, invariante un-solo-pagatore, degradazione utenze al 100%).
* **Maintain**: `models/properties.md` (campo `tipo_gestione` su Property, Room = unità locata, vincolo Room implicita), `architecture/modello-dati.md` (Room come unità locata), indici `domain/` e root aggiornati.

## 2026-07-08
* **Initialization**: creato il bundle OKF `.okf/` con struttura `architecture/`, `domain/`, `models/`, `decisions/`, `playbooks/`.
* **Creation**: concetti di dominio (Receivable, riconciliazione, generazione affitti, calcolo utenze, conguaglio, deposito, saldi fratelli, conto economico).
* **Creation**: decisioni architetturali (unificazione Receivable, "banca vince sempre", guardia allocations, segni concordi).
* **Creation**: reference strutturale dei modelli Django per le 5 app.
* **Creation**: playbook dev-setup, validazione, import storico.
