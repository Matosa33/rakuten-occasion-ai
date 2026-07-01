#!/usr/bin/env bash
# === Smoke E2E rejouable (Cycle 18.2) ===
# Déroule le parcours vendeur complet contre une stack DÉJÀ démarrée
# (docker compose up -d) et imprime PASS/FAIL par étape.
#
#   login (demo/demo)  →  upload photo  →  identify  →  price  →  describe
#
# Usage :
#   bash scripts/smoke_e2e.sh                 # cible http://127.0.0.1:${API_PORT:-8010}
#   API_BASE=http://127.0.0.1:8010 bash scripts/smoke_e2e.sh
#
# Note : on PIPE directement curl → python (pas de fichier /tmp intermédiaire) -
# le mélange chemins Git-Bash / Python Windows casse les temp files.
# Le parsing JSON est fait par python (stdin).

set -u

# --- Résolution de la base API (lit .env si présent, sinon défaut 8010) ---
API_PORT_DEFAULT=8010
if [ -f .env ]; then
  ENV_PORT=$(grep -E '^API_PORT=' .env | head -1 | cut -d= -f2 | tr -d '[:space:]')
  [ -n "${ENV_PORT:-}" ] && API_PORT_DEFAULT="$ENV_PORT"
fi
API_BASE="${API_BASE:-http://127.0.0.1:${API_PORT_DEFAULT}}"
FIXTURE="${FIXTURE:-scripts/fixtures/sample_product.jpg}"

PASS=0
FAIL=0
ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
ko()   { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
hdr()  { echo ""; echo "── $1"; }

echo "================================================================"
echo " Smoke E2E Rakuten - cible : $API_BASE"
echo "================================================================"

# --- 0. Health ---
hdr "0. Health"
HEALTH=$(curl -s --max-time 10 "$API_BASE/health")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  ok "GET /health → ok ($(echo "$HEALTH" | python -c "import sys,json;d=json.load(sys.stdin);print('models:',d.get('models_loaded'))" 2>/dev/null))"
else
  ko "GET /health (l'API est-elle démarrée et FAISS chargé ? voir 'docker compose ps')"
  echo "$HEALTH" | head -c 200
  echo ""; echo "Abandon."; exit 1
fi

# --- 1. Login ---
hdr "1. Login (demo/demo)"
TOKEN=$(curl -s --max-time 10 -X POST "$API_BASE/auth/login" -d "username=demo&password=demo" \
  | python -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$TOKEN" ] && [ "${#TOKEN}" -gt 20 ]; then
  ok "POST /auth/login → token (${#TOKEN} car.)"
else
  ko "POST /auth/login (JWT_SECRET présent dans .env ?)"
  echo "Abandon."; exit 1
fi

# --- 2. Upload photo ---
hdr "2. Upload photo"
if [ ! -f "$FIXTURE" ]; then ko "fixture absente : $FIXTURE"; echo "Abandon."; exit 1; fi
IMGID=$(curl -s --max-time 20 -X POST "$API_BASE/upload" -H "Authorization: Bearer $TOKEN" \
  -F "file=@${FIXTURE};type=image/jpeg" \
  | python -c "import sys,json;print(json.load(sys.stdin).get('image_id',''))" 2>/dev/null)
if [ -n "$IMGID" ]; then
  ok "POST /upload → image_id=$IMGID"
else
  ko "POST /upload"
  echo "Abandon."; exit 1
fi

# --- 3. Identify (photo-first) ---
hdr "3. Identify (retrieval grounded + validateur VLM)"
IDENT=$(curl -s --max-time 120 -X POST "$API_BASE/identify" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"image_ids\":[\"$IMGID\"],\"text\":\"\"}")
# On extrait top1 (asin, cat) + nb candidats + validation + prix catalogue top1
# + prix des voisins MÊME TYPE (comme le frontend) - pour un /price niveau L1.
read -r NCAND TOP1_ASIN TOP1_CAT VLM_MATCH TOP1_PRICE NEIGHBORS < <(echo "$IDENT" | python -c "
import sys, json
d = json.load(sys.stdin)
c = d.get('top_candidates', [])
v = d.get('vlm_validation') or {}
top = c[0] if c else {}
# voisins du même type fin que le top1 (filtre anti-accessoires)
key = lambda x: (x.get('category_fine') or x.get('category') or '')
tk = key(top)
nb = [str(x['price']) for x in c if key(x)==tk and x.get('price') and x['price']>0]
print(len(c), top.get('parent_asin','-'), (top.get('category') or '-'),
      v.get('match','-'), (top.get('price') or ''), ','.join(nb[:20]) or '-')
" 2>/dev/null)
if [ "${NCAND:-0}" -gt 0 ]; then
  ok "POST /identify → $NCAND candidats · top1=$TOP1_ASIN ($TOP1_CAT) · vlm_match=$VLM_MATCH"
else
  ko "POST /identify (aucun candidat - artefacts FAISS/lookup présents ?)"
  echo "$IDENT" | head -c 300; echo ""; echo "Abandon."; exit 1
fi

# --- 4. Price ---
hdr "4. Price (cascade transparente + USD→EUR)"
# On construit le payload avec catalog_price + neighbor_prices (flow réel → L1).
PRICE_PAYLOAD=$(CAT="$TOP1_CAT" ASIN="$TOP1_ASIN" CP="$TOP1_PRICE" NB="$NEIGHBORS" python -c "
import os, json
cp = os.environ.get('CP','').strip()
nb = [float(x) for x in os.environ.get('NB','').split(',') if x and x not in ('-',)]
p = {'category': os.environ['CAT'], 'condition':'bon_etat', 'parent_asin': os.environ['ASIN']}
if cp: p['catalog_price'] = float(cp)
if nb: p['neighbor_prices'] = nb
print(json.dumps(p))
")
PRICE=$(curl -s --max-time 30 -X POST "$API_BASE/price" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "$PRICE_PAYLOAD")
PRICE_EUR=$(echo "$PRICE" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('suggested_price_eur','-'),d.get('confidence_level','-'))" 2>/dev/null)
if echo "$PRICE" | grep -q 'suggested_price_eur'; then
  ok "POST /price → $PRICE_EUR €/niveau"
else
  ko "POST /price"
  echo "$PRICE" | head -c 200
fi

# --- 5. Describe ---
hdr "5. Describe (LLM rédacteur grounded)"
DESC=$(curl -s --max-time 60 -X POST "$API_BASE/describe" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parent_asin\":\"$TOP1_ASIN\",\"condition\":\"bon_etat\"}")
TITLE=$(echo "$DESC" | python -c "import sys,json;print(json.load(sys.stdin).get('title','')[:70])" 2>/dev/null)
if [ -n "$TITLE" ]; then
  ok "POST /describe → titre: « $TITLE »"
else
  ko "POST /describe"
  echo "$DESC" | head -c 200
fi

# --- Bilan ---
echo ""
echo "================================================================"
echo " Bilan : $PASS PASS / $FAIL FAIL"
echo "================================================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
