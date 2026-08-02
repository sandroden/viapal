"""
Dati anagrafici comuni a inquilini e proprietari.

Servono ai documenti legali che l'applicazione genera (atto di subentro nel
contratto, comunicazione di cessione di fabbricato ex art. 12 D.L. 59/1978):
entrambi vogliono nascita, residenza e — per il cessionario — cittadinanza,
dati che il gestionale non aveva mai avuto bisogno di conoscere.

``nominativo`` resta il campo canonico (ordinamenti, ``__str__``, percorsi di
upload, frontend, email): ``cognome``/``nome`` gli stanno accanto e non vengono
sincronizzati automaticamente. Derivarli con uno split sullo spazio è sbagliato
sui cognomi composti e sui nomi non italiani, e un atto legale non si firma con
un'euristica.
"""
from django.db import models


class AnagraficaPersonaMixin(models.Model):
    """Nascita e residenza di una persona fisica.

    Tutti i campi sono facoltativi: si compilano quando servono, e finché
    mancano il generatore di documenti li elenca fra i "dati mancanti"
    indicando dove inserirli.
    """

    cognome = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="cognome",
        help_text="Separato dal nome perché i moduli ufficiali hanno due caselle distinte.",
    )
    nome = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="nome",
    )
    data_nascita = models.DateField(
        null=True,
        blank=True,
        verbose_name="data di nascita",
    )
    comune_nascita = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="comune di nascita",
        help_text="Per chi è nato all'estero: la città estera.",
    )
    provincia_nascita = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="provincia o nazione estera di nascita",
        help_text=(
            "Sigla della provincia (es. MB) oppure nazione estera: il modulo "
            "di cessione di fabbricato ha una casella sola per entrambi."
        ),
    )
    cittadinanza = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="cittadinanza",
    )
    residenza_via = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="residenza: via e numero civico",
    )
    residenza_comune = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="residenza: comune",
    )
    residenza_provincia = models.CharField(
        max_length=4,
        blank=True,
        verbose_name="residenza: provincia",
    )
    residenza_cap = models.CharField(
        max_length=8,
        blank=True,
        verbose_name="residenza: CAP",
    )

    class Meta:
        abstract = True

    @property
    def nome_completo(self) -> str:
        """``Cognome Nome`` se disponibili, altrimenti ``nominativo``."""
        completo = f"{self.cognome} {self.nome}".strip()
        return completo or self.nominativo
