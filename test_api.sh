#!/usr/bin/env bash
set -euo pipefail

# ---- Config -------------------------------------------------------------
BASE="${BASE:-http://localhost:8090}"
API="${API:-7d1fd70c60ac827d2bddc4de879804e8}"
USER_NAME="${USER_NAME:-jiri.cechura}"
MEM_FILE="${MEM_FILE:-/home/master/otec_fura/memory/jiri/private.jsonl}"

# ---- Colors -------------------------------------------------------------
GREEN="\033[1;32m"; RED="\033[1;31m"; YELLOW="\033[1;33m"; BLUE="\033[1;34m"; NC="\033[0m"
ok(){   echo -e "${GREEN}✔ $*${NC}"; }
fail(){ echo -e "${RED}✖ $*${NC}"; }
info(){ echo -e "${BLUE}i${NC} $*"; }
warn(){ echo -e "${YELLOW}! $*${NC}"; }

# ---- Helpers ------------------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1 || { warn "'$1' není nainstalované"; return 1; }; }

curl_json() { # url headers... -> prints body, sets global HTTP
  local url="$1"; shift
  HTTP=$(curl -sS -o /tmp/resp.json -w "%{http_code}" "$url" "$@") || true
  cat /tmp/resp.json
}

assert_code() { # expected
  [[ "$HTTP" == "$1" ]] && ok "HTTP $HTTP" || { fail "HTTP $HTTP (čekáno $1)"; return 1; }
}

show_body() {
  if need jq; then jq . /tmp/resp.json || cat /tmp/resp.json; else cat /tmp/resp.json; fi
}

# ---- Tests --------------------------------------------------------------
test_root(){
  info "Root /"
  curl_json "$BASE/" -H "Authorization: Bearer $API"
  assert_code 200 || return 1
}

test_openapi(){
  info "OpenAPI /openapi.json"
  curl_json "$BASE/openapi.json" -H "Authorization: Bearer $API"
  assert_code 200 || return 1
  need jq && jq '.paths | keys' /tmp/resp.json || true
}

test_user_ok(){
  info "User /user (OK key)"
  curl_json "$BASE/user" -H "Authorization: Bearer $API"
  assert_code 200 || return 1
  show_body
}

test_user_bad(){
  info "User /user (BAD key)"
  curl_json "$BASE/user" -H "Authorization: Bearer BAD"
  assert_code 403 || return 1
  show_body
}

test_user_missing(){
  info "User /user (missing key)"
  curl_json "$BASE/user"
  assert_code 401 || return 1
  show_body
}

test_context_nowrite(){
  info "POST /get_context (bez zápisu)"
  curl_json "$BASE/get_context" \
    -H "Authorization: Bearer $API" \
    -H "Content-Type: application/json" \
    --data "{\"query\":\"zkouska kontextu\",\"user\":\"$USER_NAME\"}"
  assert_code 200 || return 1
  show_body
}

test_context_write(){
  info "POST /get_context (se zápisem)"
  local marker="test-zapis-$(date +%s)"
  curl_json "$BASE/get_context" \
    -H "Authorization: Bearer $API" \
    -H "Content-Type: application/json" \
    --data "{\"query\":\"$marker\",\"user\":\"$USER_NAME\",\"remember\":true}"
  assert_code 200 || return 1
  show_body
  echo "$marker" >/tmp/_marker.txt
}

verify_memory(){
  info "Ověření zápisu do paměti: $MEM_FILE"
  if [[ -f "$MEM_FILE" ]]; then
    tail -n 5 "$MEM_FILE" | sed 's/^/  /'
    if [[ -s /tmp/_marker.txt ]]; then
      local m; m=$(cat /tmp/_marker.txt)
      if grep -Fq "$m" "$MEM_FILE"; then ok "marker nalezen v paměti"; else fail "marker v paměti nenalezen"; return 1; fi
    fi
  else
    fail "Soubor paměti neexistuje: $MEM_FILE"; return 1
  fi
}

# ---- Run ---------------------------------------------------------------
echo -e "${YELLOW}Testuji Otec Fura API na ${BASE}${NC}"
rc=0
test_root            || rc=1
test_openapi         || rc=1
test_user_ok         || rc=1
test_user_bad        || rc=1
test_user_missing    || rc=1
test_context_nowrite || rc=1
test_context_write   || rc=1
verify_memory        || rc=1

echo
if [[ $rc -eq 0 ]]; then ok "Vše PROŠLO ✅"; else fail "Něco selhalo ❌ (rc=$rc)"; fi
exit $rc
