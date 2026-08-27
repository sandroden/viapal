"""Lead finti per sviluppare la pagina senza far girare il bot.

Senza questo, ogni ritocco alla pagina costerebbe uno scrape vero di Facebook.
I testi sono inventati e i link puntano al gruppo, non a persone reali.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from leads.models import Lead
from properties.context import resolve_property_cli

ESEMPI = [
    {
        "post_id": "seed-001",
        "author_name": "Giulia Ferrari",
        "testo": (
            "Ciao a tutti! Cerco una stanza singola in zona Monza centro o "
            "vicino alla stazione, budget massimo 480 tutto compreso. "
            "Lavoro in ospedale, sono tranquilla e ordinata. Disponibile da "
            "metà settembre. Grazie!"
        ),
        "analisi": {
            "zona": "Monza centro",
            "budget_max": 480,
            "disponibile_da": "metà settembre",
            "stanze_compatibili": ["S2", "S4"],
            "motivo": "Cerca singola in zona, budget compatibile con S2 e S4.",
        },
        "commento_proposto": "Ciao Giulia, ti ho scritto in privato: abbiamo una singola libera a Monza 👋",
        "privato_proposto": (
            "Ciao Giulia, ho letto il tuo post. Abbiamo una stanza singola libera "
            "in Via Palestrina, a Monza, 450€ + 40€ di spese condominiali "
            "(riscaldamento incluso). Qui trovi le foto: https://viapal.e-den.it/g/palestrina\n"
            "Se ti interessa possiamo sentirci quando preferisci."
        ),
    },
    {
        "post_id": "seed-002",
        "author_name": "Marco Bianchi",
        "testo": (
            "Buongiorno, io e la mia ragazza cerchiamo una camera doppia in "
            "Brianza, max 600 euro. Siamo entrambi lavoratori, no animali. "
            "Ci servirebbe da ottobre."
        ),
        "analisi": {
            "zona": "Brianza",
            "budget_max": 600,
            "disponibile_da": "ottobre",
            "stanze_compatibili": ["S1"],
            "motivo": "Coppia per la doppia S1, budget sopra il canone richiesto.",
        },
        "commento_proposto": "Ciao Marco, ti ho mandato un messaggio: abbiamo una doppia libera 👋",
        "privato_proposto": (
            "Ciao Marco, abbiamo una camera doppia libera in Via Palestrina a Monza, "
            "540€ + 40€ di spese condominiali. Le foto sono qui: "
            "https://viapal.e-den.it/g/palestrina"
        ),
    },
    {
        "post_id": "seed-003",
        "author_name": "Ana Popescu",
        "testo": (
            "Salve, cerco stanza singola a Monza o Villasanta per me, "
            "lavoro come OSS. Budget 400-450. Grazie mille a chi risponde."
        ),
        "analisi": {
            "zona": "Monza / Villasanta",
            "budget_max": 450,
            "disponibile_da": "subito",
            "stanze_compatibili": ["S4"],
            "motivo": "Singola in zona, budget al limite: compatibile solo con S4.",
        },
        "commento_proposto": "Ciao Ana, ti ho scritto in privato 👋",
        "privato_proposto": (
            "Ciao Ana, abbiamo una singola libera in Via Palestrina a Monza, "
            "410€ + 40€ di spese. Foto qui: https://viapal.e-den.it/g/palestrina"
        ),
    },
    {
        "post_id": "seed-004",
        "author_name": "Davide Rinaldi",
        "testo": (
            "Cerco posto letto o stanza in condivisione a Monza, anche "
            "temporaneo per 3 mesi. Sono uno studente del Politecnico."
        ),
        "analisi": {
            "zona": "Monza",
            "budget_max": None,
            "disponibile_da": "subito",
            "stanze_compatibili": ["S2"],
            "motivo": "Zona giusta ma chiede breve periodo: da valutare.",
        },
        "commento_proposto": "Ciao Davide, ti ho scritto 👋",
        "privato_proposto": (
            "Ciao Davide, abbiamo una singola libera a Monza. Noi però affittiamo "
            "con contratto annuale, non per tre mesi: se ti va bene lo stesso, "
            "scrivimi pure."
        ),
    },
]


class Command(BaseCommand):
    help = "Crea lead di esempio per sviluppare la pagina senza far girare il bot."

    def add_arguments(self, parser):
        parser.add_argument("--property", dest="property", default=None)
        parser.add_argument(
            "--pulisci",
            action="store_true",
            help="Cancella i lead di esempio (post_id seed-*) invece di crearli.",
        )

    def handle(self, *args, **options):
        prop = resolve_property_cli(options["property"])
        if options["pulisci"]:
            n, _ = Lead.objects.filter(property=prop, post_id__startswith="seed-").delete()
            self.stdout.write(self.style.SUCCESS(f"Cancellati {n} lead di esempio."))
            return

        ora = timezone.now()
        for i, dati in enumerate(ESEMPI):
            Lead.objects.update_or_create(
                property=prop,
                post_id=dati["post_id"],
                defaults={
                    "group_id": "1234567890",
                    "group_label": "Affitti Monza e Brianza",
                    "author_url": "https://www.facebook.com/groups/1234567890",
                    "permalink": f"https://www.facebook.com/groups/1234567890/posts/{dati['post_id']}/",
                    "link_messenger": "https://m.me/",
                    "seen_at": ora - timedelta(hours=i * 3),
                    **{
                        k: v
                        for k, v in dati.items()
                        if k in {"author_name", "testo", "analisi", "commento_proposto", "privato_proposto"}
                    },
                },
            )
        self.stdout.write(
            self.style.SUCCESS(f"{len(ESEMPI)} lead di esempio su «{prop}».")
        )
