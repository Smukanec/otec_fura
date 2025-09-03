# Otec FURA (konsolidovaná)

Veřejná vrstva (wrapper) + původní FURA app (mount pod `/core`).

## Rychlý start (lokálně)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt  # min: fastapi, uvicorn, httpx
cp .env.example .env             # vyplň MODEL_API_BASE, MODEL_API_KEY atd.
uvicorn app_ask:app --host 0.0.0.0 --port 8090
```

## Správa uživatelů

Uživatelé jsou uloženi v souboru `data/users.json`. K jejich vytváření a
schvalování slouží jednoduché skripty.

### Vytvoření uživatele

```bash
./create_user.sh -u <jméno> -e <email>
```

Skript se doptá na heslo a vygeneruje API klíč. Pokud přidáte volbu
`--approve`, bude uživatel schválen rovnou.

### Schválení (uvolnění) uživatele

Pokud není uživatel schválen při vytvoření, lze to provést následně
upravením `data/users.json` nebo pomocí administračního nástroje:

```bash
python admin_tools.py approve <jméno>
```

Seznam uživatelů a další možnosti:

```bash
python admin_tools.py list       # vypíše všechny uživatele
python admin_tools.py show <jméno>  # zobrazí API klíč
```

