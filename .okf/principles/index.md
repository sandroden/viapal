# Principi in vigore

Regole di progetto che non descrivono codice e non hanno una `resource:`:
non driftano per commit, cambiano solo per decisione esplicita. Vanno tenute
in contesto sempre (l'hook di sessione inietta questo indice) e ogni modifica
va confrontata con esse; uno scostamento si dichiara nel commit.

* [Tutto utilizzabile dal frontend](tutto-da-frontend.md) - ogni operazione di proprietari/inquilini ha endpoint e pagina; l'admin Django è fallback del superuser. Violazione tipica: azione o campo editabile solo in admin.
