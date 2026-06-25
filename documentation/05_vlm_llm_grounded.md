# 05 — VLM & LLM ancrés (RAG grounded)

> Les IA génératives du projet: l'une **voit** (la photo), l'autre **rédige** (l'annonce).
> Toutes deux sont **bridées par des faits réels** pour ne pas inventer. C'est le garde-fou
> anti-hallucination de bout en bout.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
- **VLM** (*Vision-Language Model*): une IA qui **comprend les images**. Chez nous elle (a) lit
 la photo du vendeur → **titre probable + attributs** (marque, couleur, capacité…), et (b)
 **vérifie**: « la photo du vendeur correspond-elle à l'image catalogue du candidat ? ».
- **LLM** (*Large Language Model*): une IA qui **écrit du texte** → titre + description d'annonce.
- **RAG** (*Retrieval-Augmented Generation*): au lieu de laisser l'IA écrire « de mémoire » (où
 elle invente), on lui **fournit les faits** (la vraie fiche du produit retrouvé) et on lui
 demande de **ne rédiger qu'à partir de ça**. C'est l'« ancrage » (grounding).

### Pourquoi c'est crucial
Un LLM **hallucine par construction**: il complète du texte plausible, vrai ou faux. Si on lui
dit « écris une annonce pour un iPhone 13 », il **inventera** des specs. Le RAG transforme
« générer » (libre, hallucinable) en « reformuler ces faits-ci » (contraint, vérifiable).

### Pour l'expert
- On **sépare les rôles**: le **retrieval identifie** (cf. *Retrieval*), le **VLM vérifie**, le
 **LLM rédige**. Aucun génératif ne décide de l'identité → on supprime la principale source
 d'hallucination.
- On peut **tester l'ancrage**: un token présent dans la description générée doit appartenir à
 {tokens du prompt} ∪ {tokens du grounding} — sinon c'est une invention.

---

## 2. État de l'art

- Le **RAG** est l'un des moyens les plus efficaces d'ancrer un LLM dans des faits (contexte
 fourni au moment de générer).
- Bonnes pratiques anti-hallucination: **récupération de qualité**, **règles d'ancrage
 explicites** dans le prompt (« n'utilise que le contexte fourni »), **sortie structurée (JSON)**
 qui contraint et facilite la validation.
- Les **VLM hallucinent aussi**; le RAG les contraint à s'appuyer sur la connaissance fournie.
- Limite connue: un modèle peut mal interpréter une source ou ne pas reconnaître qu'elle ne
 contient pas la réponse.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Le client (`src/llm/openrouter_client.py`)
- Modèle par défaut **`google/gemma-4-31b-it`** (vision-capable), via **OpenRouter**.
- `chat_completion`: **température 0,4** (peu créatif, factuel), **max_tokens 1024**.
- `is_available`: présence de la clé → sinon **dégradation propre** (mock).
- `translate_to_english`: traduit la requête FR→EN avant la recherche (catalogue anglais).

### Extraction photo (`src/vlm/photo_extraction.py`)
- `extract(photo_paths)` → `PhotoExtraction{title_guess, attributes}`.
- **`MAX_PHOTOS_PER_CALL = 4`**: toutes les vues passent dans **UN seul appel** (moins cher,
 contexte commun); photos encodées en **data-URL base64**.
- Prompt → **JSON** `{title, attributes{brand, color, capacity, model, visible_text}}`; parsing
 **tolérant** (fences ```…```, prose autour). `PhotoExtractionUnavailable` si pas de clé.

### Vérificateur visuel F0.4 (`src/vlm/validator.py`)
- `validate_top1(user_photos, catalog_image_url, title)` → `VLMValidation{match, confidence,
 reason}`, **JSON strict**. **`MAX_USER_PHOTOS = 2`** (le match se joue sur la vue principale).
- **Best-effort, jamais bloquant**: `None` si pas de photo, pas d'image catalogue, ou VLM
 down → l'identification continue.

### Rédacteur RAG (`src/llm/01_prompt_templates.py` + `02_rag_grounded_writer.py`)
- Prompt structuré: **`RÔLE → INSTRUCTION → CONTEXTE (faits) → SORTIE JSON`**, avec l'instruction
 « n'utilise que le contexte fourni » + l'état vendeur exact (`{seller_condition}`).
- `extract_useful_sentences(reviews, top_n)`: sélectionne les phrases de grounding (triées par
 longueur décroissante) issues de la **description catalogue réelle**.
- **Abstraction `LLMWriter`**: `OpenRouterWriter` (réel) **ou** `MockLLMWriter` — bascule
 automatique selon la clé. La sortie `GeneratedListing` garde la **liste des phrases de
 grounding utilisées** (traçabilité de l'ancrage).

---

## 4. Résultats (mesurés / observés)

- **Preuve d'ancrage**: sur un produit testé, « **Snapdragon 732G** » apparaît dans l'annonce
 **parce que ça vient de la fiche réelle** (grounding) — pas du titre, pas de la mémoire du LLM.
- **Vérificateur visuel** branché: photo iPhone → `{match: true, confidence: 1.0, reason:
 "diagonal dual-camera layout"}` (raison **factuelle, observable**).
- **Dégradation propre vérifiée**: sans clé OpenRouter, `/describe` bascule en mock (titre
 générique détectable), l'identification + le prix (locaux) continuent.
- Éval RAG tracée (`reports/07_rag_eval/rag_grounded_eval.json`); tests `test_llm_rag`,
 `test_llm_writer`, `test_describe_openrouter`, `test_vlm_validator`.
- **Mesure « richesse d'entrée » sur 92 vraies annonces** (`reports/05_retrieval/photo_richness_bench.md`):
 **une seule photo < plusieurs photos** (catégorie correcte 0,82 → 0,89) — la lecture multi-vues
 par le VLM extrait mieux marque + modèle. En revanche la **métadonnée vendeur ajoute peu** (le VLM
 capte déjà l'essentiel sur les photos), et **traduire la requête entière la dégrade** (la
 traduction réécrit le bon titre produit par le VLM). Décision pilotée par la mesure : **on ne
 traduit pas la requête combinée**. Résultat honnête, y compris là où il infirme une intuition.

> 📊 **Chiffres/faits slide**: « extraction + validation par Gemma 4 31B (4 vues en 1 appel,
> JSON, température 0,4) », « preuve d'ancrage: Snapdragon 732G vient du grounding », « validateur
> visuel: match + raison factuelle », « dégradation propre (mock) ». 📸 **Capture**: l'annonce
> générée à côté de la fiche catalogue (specs qui correspondent) + le badge de correspondance
> visuelle dans l'app.

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **RAG avec règles d'ancrage explicites + sortie JSON** → bonnes pratiques exactes.
- ✅ **Rôles séparés** (retrieval identifie / VLM vérifie / LLM rédige) → supprime la principale
 source d'hallucination.
- ✅ **Best-effort partout**: le validateur et l'extraction ne cassent jamais le flux.
- ✅ **Dégradation propre** (mock) + **abstraction Writer** → robustesse de démo et testabilité.
- ✅ Optimisation coût: 4 vues en **un** appel, température basse (factuel).

**Limites assumées:**
- **Dépendance API externe** (Gemma via OpenRouter): coût + latence + disponibilité. Atténuée
 par le mock, mais c'est une dépendance.
- **Grounding sur la description, pas encore sur les avis**: enrichir avec les *reviews* réelles
 est un gain futur (jointure lazy à faire).
- **Le VLM confond des générations proches** (iPhone 13/14): mesuré et **assumé**; la facette
 Akinator + l'humain tranchent. Pas de prétention à 100 %.
- **Pas de citation passage-par-passage** dans l'annonce (bonne pratique avancée) → amélioration.

---

## 6. Références
- Prompting Guide — *Retrieval Augmented Generation (RAG) for LLMs* — https://www.promptingguide.ai/research/rag
- Lewis et al. — *Retrieval-Augmented Generation (RAG, papier fondateur)* — https://arxiv.org/abs/2005.11401
- arXiv 2407.12858 — *Grounding and evaluation for LLMs (survey)* — https://arxiv.org/pdf/2407.12858
- arXiv 2501.03995 — *RAG-Check: evaluating multimodal RAG* — https://arxiv.org/pdf/2501.03995

---

### En une phrase (pour la défense)
*« Nos IA génératives ne devinent jamais: le produit est d'abord retrouvé dans le catalogue,
puis un VLM (Gemma 4 31B) vérifie visuellement et un LLM rédige uniquement à partir de la fiche
réelle (grounding explicite + sortie JSON, température 0,4). On le prouve: une spec comme
"Snapdragon 732G" vient du contexte fourni, pas de la mémoire du modèle. Et tout dégrade
proprement (mock) si l'API tombe. »*
