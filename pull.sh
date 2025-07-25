#!/bin/bash

# Nastavení identity (jednorázově, pokud ještě není)
git config --global user.name "Smukanec"
git config --global user.email "jiri.cechura@gmail.com"

# Přepnutí do repozitáře
cd "$(dirname "$0")"

# Git pull s merge (bez rebase/fast-forward)
git pull --no-rebase --no-ff

# Pokud je potřeba commitnout merge
if git diff --cached --quiet; then
  echo "✅ Repo je aktuální."
else
  git commit -m "Automatický merge přes pull.sh"
fi
