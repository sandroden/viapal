"""Test del parser dei PDF bolletta (``riparsa_bollette_pdf.estrai_da_testo``).

I fixture sono estratti *anonimizzati* del testo prodotto da
``pdftotext -layout`` sulle bollette reali (nomi, CF, POD/PDR e indirizzi
sostituiti; importi, date e consumi lasciati intatti). Si testa il testo e non
il PDF per non versionare documenti con dati personali.
"""
import datetime
from decimal import Decimal

from billing.management.commands.riparsa_bollette_pdf import estrai_da_testo

# Iren energia elettrica — estratto reale (bolletta di maggio 2026).
IREN_LUCE = """
                                          Numero cliente 100000000000 Numero contratto 10000000

                                          I miei dati
                                          Cliente                       C.F. / P.IVA
                                          Mario Rossi                   RSSMRA80A01F205X

Fattura n. 38502606937372 *
Emessa in data: 04 giugno 2026
Documento non valido ai fini IVA – copia analogica di fattura elettronica
* numero fattura elettronica valida ai fini fiscali                    VIA DEI TEST 1 INT 0
                                                                       20834 NOVA MILANESE MB

** Periodo di riferimento:
01 MAGGIO 2026 - 31 MAGGIO 2026
                              La mia bolletta

                              ENERGIA ELETTRICA                 Totale da pagare               53,96 €
                              MERCATO LIBERO                              Scadenza 19/06/2026

 Nome offerta                          Condizioni economiche dell'offerta    Consumo totale fatturato nel periodo **
 Iren prima scelta luce fissa          Scadenza: 30/04/2027                  130 kWh

IREN MERCATO S.p.A. – Sede Legale e Direzione Piazza Giambattista Raggi 6, 16137 Genova
                                                             Pag. 1 di 8
                              POD                        Potenza impegnata
                              IT001E99999999             3,0 kW

              Scontrino dell'energia
                                                        QUANTITA'        PREZZO MEDIO      IMPORTO
     ENERGIA ATTIVA                                      130 kWh x      0,159615 €/kWh     20,75 €
     Totale bolletta                                                                       53,96 €
     Totale da pagare                                                                      53,96 €

     TOTALE FORNITURA DI ENERGIA ELETTRICA E IMPOSTE            Importo €            49,05
"""

# Iren gas: variante costruita sul layout luce (stesso impianto di pagina),
# usata per verificare che PDR/Smc portino a `prodotto="gas"`.
IREN_GAS = """
Fattura n. 38502606937999 *
Emessa in data: 07 luglio 2026

** Periodo di riferimento:
01 MAGGIO 2026 - 30 GIUGNO 2026
                              La mia bolletta

                              GAS NATURALE                      Totale da pagare               84,20 €

 Nome offerta                          Condizioni economiche dell'offerta    Consumo totale fatturato nel periodo **
 Iren prima scelta gas fissa           Scadenza: 30/04/2027                  46 Smc

IREN MERCATO S.p.A. – Sede Legale e Direzione Piazza Giambattista Raggi 6, 16137 Genova
                              PDR                        Categoria d'uso
                              03400000099999             C1

     Totale da pagare                                                                      84,20 €
"""

# Magis Energia gas — estratto reale (bolletta 18/05–30/06/2026).
MAGIS_GAS = """
               Bolletta per la fornitura di gas
               naturale
               Mercato libero

         Codice Cliente: 0600000000                            MARIO ROSSI
         MARIO ROSSI                                           VIA DEI TEST 1
         Codice Fiscale: RSSMRA80A01F205X                      20865 USMATE VELATE MB

Fattura n° 82602703805 del 24/07/2026                    Le bollette precedenti ci risultano pagate.

(Numero fattura elettronica valida ai fini fiscali: 82602703805)

        Periodo oggetto di fatturazione                  Modalità di pagamento:

        Dal 18/05/2026 al 30/06/2026
                                                         Consumo annuo aggiornato (Smc): 36,000
                                                         Dal 30/06/2025 al 30/06/2026

        Totale da pagare:                                800.55.22.77 Numero verde (RETIPIU SRL)

        162,94 €                                         24 ore su 24 tutti i giorni dell'anno

        Consumi 35,969 Smc                               Numero verde 800.552.866
        di cui stimati 0 Smc                             Sito ufficiale magisenergia.it

Magis Energia S.p.A. - Sede legale e amministrativa      Lungadige Galtarossa, 8 37133 Verona
                                                                                Pagina 1 di 6
                SCONTRINO                               BOX DELL'OFFERTA
                DELL'ENERGIA                            Spesa per la vendita di gas naturale

         PDR: 15330000000000

Quota per consumi                     Prezzo medio          Importo
35,969 Smc                            0,723939 €/Smc         26,04 €

Totale da pagare                          162,94 €
"""

# Edison gas: la prosa sui bonus sociali cita l'energia elettrica; prima del
# riconoscimento via PDR queste bollette venivano classificate "luce".
EDISON_GAS = """
                MERCATO LIBERO          novembre 2023 - dicembre 2023                 GAS NATURALE
 20900, MONZA MB                        Cliente: Domestico                     PDR 03410000021887

  Gentile Cliente, nel caso in cui lei avesse diritto ai bonus sociali per la fornitura di
  energia elettrica, gas naturale e acqua, i dati personali trasmessi con il modello
"""


def test_iren_luce():
    dati = estrai_da_testo(IREN_LUCE)
    assert dati["importo"] == Decimal("53.96")
    assert dati["periodo_da"] == datetime.date(2026, 5, 1)
    assert dati["periodo_a"] == datetime.date(2026, 5, 31)
    assert dati["data_emissione"] == datetime.date(2026, 6, 4)
    assert dati["numero_fattura_reale"] == "38502606937372"
    assert dati["consumo"] == Decimal("130")
    assert dati["fornitore"] == "Iren"
    assert dati["prodotto"] == "luce"


def test_iren_gas():
    dati = estrai_da_testo(IREN_GAS)
    assert dati["importo"] == Decimal("84.20")
    assert dati["periodo_da"] == datetime.date(2026, 5, 1)
    assert dati["periodo_a"] == datetime.date(2026, 6, 30)
    assert dati["data_emissione"] == datetime.date(2026, 7, 7)
    assert dati["consumo"] == Decimal("46")
    assert dati["fornitore"] == "Iren"
    assert dati["prodotto"] == "gas"


def test_magis_gas():
    dati = estrai_da_testo(MAGIS_GAS)
    assert dati["importo"] == Decimal("162.94")
    assert dati["periodo_da"] == datetime.date(2026, 5, 18)
    assert dati["periodo_a"] == datetime.date(2026, 6, 30)
    assert dati["data_emissione"] == datetime.date(2026, 7, 24)
    assert dati["numero_fattura_reale"] == "82602703805"
    # "Consumi 35,969 Smc", non il consumo annuo (36,000) né i decimali
    # spezzati dal fallback posizionale.
    assert dati["consumo"] == Decimal("35.969")
    assert dati["fornitore"] == "Magis Energia"
    assert dati["prodotto"] == "gas"


def test_pdr_batte_la_prosa_sull_energia_elettrica():
    assert estrai_da_testo(EDISON_GAS)["prodotto"] == "gas"


def test_testo_non_riconosciuto():
    dati = estrai_da_testo("Un documento qualsiasi, senza importi né periodi.")
    assert dati["importo"] is None
    assert dati["periodo_da"] is None
    assert dati["prodotto"] is None
