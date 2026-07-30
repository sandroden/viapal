# Procedura data breach

*Documento interno. Una "violazione di dati personali" è ogni evento che
comporti distruzione, perdita, modifica, divulgazione o accesso non
autorizzato ai dati: compromissione del server, credenziali rubate, URL di
documenti esposti pubblicamente, perdita di un backup, invio di documenti al
destinatario sbagliato.*

## 1. Rilevazione e contenimento (subito)

- Contenere: revocare credenziali/sessioni compromesse, chiudere
  l'esposizione (es. bloccare il serving pubblico), isolare il server se
  necessario.
- Fotografare l'accaduto: cosa, quando, quali dati, quali interessati, log
  rilevanti. Conservare le evidenze.

## 2. Valutazione (entro 24h)

Domande chiave:

- Quali categorie di dati? (documenti d'identità ⇒ rischio furto d'identità
  ⇒ rischio **alto** quasi per definizione)
- Quanti interessati? Dati di quali titolari (miei / di proprietari
  accreditati)?
- La violazione è cessata? I dati sono stati effettivamente acceduti o solo
  esposti?

## 3. Notifiche

| Caso | Azione | Termine |
|---|---|---|
| Rischio per gli interessati (regola: quasi sempre, se coinvolti documenti) | Notifica al **Garante** tramite la procedura telematica su servizi.garanteprivacy.it | **72 ore** dalla scoperta |
| Rischio elevato (documenti d'identità, credenziali) | Comunicazione **agli interessati** (e-mail chiara: cosa è successo, cosa fare — es. attenzione a tentativi di phishing/furto d'identità) | Senza ingiustificato ritardo |
| Dati di un proprietario accreditato (io = responsabile) | Informare **il titolare** (il proprietario) con le informazioni per la sua eventuale notifica | **48 ore** (da accordo art. 28) |
| Rischio improbabile (es. dato già pubblico, cifratura robusta) | Nessuna notifica, ma registrazione interna motivata | — |

## 4. Registro delle violazioni (sempre, anche senza notifica)

Annotare in coda a questo file: data, descrizione, dati e interessati
coinvolti, valutazione del rischio, misure prese, notifiche effettuate (o
motivo della non-notifica).

## 5. Post-mortem

Rimuovere la causa (fix, hardening) e aggiornare, se serve, registro dei
trattamenti e misure di sicurezza.

---

## Registro violazioni

| Data | Descrizione | Rischio | Notifiche | Misure |
|---|---|---|---|---|
| — | — | — | — | — |
