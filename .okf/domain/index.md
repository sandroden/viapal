# Dominio — logica contabile

Conoscenza non ricostruibile dai soli `models.py`: algoritmi, regole, flussi.

* [Receivable](receivable.md) - l'addebito unificato, cuore del modello.
* [Riconciliazione bonifici](riconciliazione.md) - matching e allocazione M:N BT↔Receivable.
* [Generazione affitti](generazione-affitti.md) - canoni mensili, pro-rata, quota condominio.
* [Calcolo utenze](calcolo-utenze.md) - bolletta→periodo, pro-rata giorni, pinning, avvisi.
* [Conguaglio](conguaglio.md) - conguaglio periodico e previsionale.
* [Deposito](deposito.md) - versamento e restituzione cauzionale.
* [Saldi proprietari](saldi-proprietari.md) - contabilità inter-proprietario e settlement.
* [Conto economico](conto-economico.md) - cassa vs competenza e il ponte tra i due.
* [Solleciti e registro comunicazioni](solleciti.md) - riepilogo addebiti agli inquilini e archivio di cosa è stato inviato.
* [Fascicolo documenti](fascicolo-documenti.md) - checklist documenti inquilino, stati derivati, visore interno.
* [Unità intera](unita-intera.md) - Property.tipo_gestione, Room come unità locata, un solo pagatore.
* [Conti bancari per immobile](conti-per-immobile.md) - il conto è unico, ma dove è in uso è esplicito: su questo poggia l'isolamento dei movimenti.
