"""Patch jmb.filters per Django >= 5.1.

`AdvancedSearchChangeList.get_queryset` rimuove i nomi dei filtri dal dict
`self.params` ma non da `self.filter_params` (introdotto in Django 5.1 e
usato da `ChangeList.get_filters_params` come sorgente per `lookup_params`).

Conseguenza: i filtri che NON sono lookup-validi a livello ORM (es. il
`scadenza__range=this_year` di `DateRangeFilter`, dove "this_year" e' una
choice del filterset, non una stringa di range data) sopravvivono fino a
`ChangeList.get_filters` e fanno saltare la pagina con
`IncorrectLookupParameters` -> redirect a `?e=1`.

Patchiamo il metodo per pulire anche `filter_params`. Da rimuovere quando
jmb.filters >= versione che integra il fix upstream.
"""
from __future__ import annotations


def install_filter_params_patch() -> None:
    from jmb.filters.admin.options import AdvancedSearchChangeList

    if getattr(AdvancedSearchChangeList, "_viapal_filter_params_patched", False):
        return

    original_get_queryset = AdvancedSearchChangeList.get_queryset

    def patched_get_queryset(self, request):
        if (
            hasattr(self.model_admin, "search_form")
            and self.model_admin.search_form.is_valid()
            and hasattr(self, "filter_params")
        ):
            for name in self.model_admin._lookup_names:
                self.filter_params.pop(name, None)
        return original_get_queryset(self, request)

    AdvancedSearchChangeList.get_queryset = patched_get_queryset
    AdvancedSearchChangeList._viapal_filter_params_patched = True
