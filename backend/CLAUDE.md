# Progetto Django — core

## Package manager

Questo progetto usa **uv** come package manager.

- Aggiungere dipendenze: `uv add <package>`
- Aggiungere dipendenze dev: `uv add --dev <package>`
- Eseguire comandi: `uv run manage.py <command>`
- Sync ambiente: `uv sync`

## Struttura

- Le app Django vanno nella cartella `apps/`
- `manage.py` ha già `sys.path.insert(0, "./apps")` quindi le app in `apps/` sono importabili direttamente
- Settings in `core/settings/` (cartella con base, dev, staging, production)
- L'ambiente è determinato dalla variabile `ENV` (dev/staging/production)

## Comandi utili

```bash
uv run manage.py runserver       # Avvia il server di sviluppo
uv run manage.py makemigrations  # Crea le migrazioni
uv run manage.py migrate         # Applica le migrazioni
uv run manage.py createsuperuser # Crea un superuser
uv run manage.py shell           # Shell interattiva (ipython)
```

## Repository
* ogni feature deve essere salvata separatamente
* se comincio una feature con file non committati, o procedi a committare o chiedi
* se correggi una feature precedentemente chiusa, possibilmemte cerca di andare in amend 
