# 05 — VLM & LLM ancrés (RAG grounded)

> Les IA génératives du projet : l'une **voit** (la photo), l'autre **rédige** (l'annonce).
> Toutes deux sont **bridées par des faits réels** pour qu'elles n'inventent pas.

---

## 1. La technologie : qu'est-ce que c'est ?

- **VLM** (*Vision-Language Model*) : une IA qui **comprend les images**. Chez nous elle lit
  la photo du vendeur et en sort un **titre probable + des attributs** (marque, couleur,
  texte visible). Elle sert aussi de **vérificateur** : « la photo du vendeur correspond-elle
  à l'image du produit candidat ? ».
- **LLM** (*Large Language Model*) : une IA qui **écrit du texte**. Chez nous elle rédige le
  titre et la description de l'annonce.
- **RAG** (*Retrieval-Augmented Generation*) : au lieu de laisser l'IA écrire « de mémoire »
  (où elle invente), on lui **fournit les faits** (la vraie fiche du produit retrouvé) et on
  lui demande de **ne rédiger qu'à partir de ça**. C'est l'« ancrage » (grounding).

---

## 2. État de l'art

- **Le RAG est l'un des moyens les plus efficaces** d'« ancrer » un modèle dans des faits :
  on lui donne le contexte pertinent au moment de générer.
- Bonnes pratiques d'un RAG anti-hallucination :
  - **récupération de qualité** (bons embeddings, bon découpage),
  - **règles d'ancrage explicites** dans le prompt : *« ne déduis que du contexte fourni »*,
  - **format de sortie structuré** (JSON) qui contraint le modèle et facilite la validation.
- **Les VLM hallucinent aussi** ; le RAG réduit le problème en les contraignant à s'appuyer
  sur la connaissance fournie.
- Limite connue : un modèle peut mal interpréter une source ou ne pas reconnaître qu'elle ne
  contient pas la réponse.

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Extraction photo | `src/vlm/photo_extraction.py` | la photo → titre + attributs (JSON) |
| Vérificateur visuel | `src/vlm/validator.py` | photo vendeur × image catalogue → {correspond, confiance, raison} |
| Prompts ancrés | `src/llm/01_prompt_templates.py` | structure `RÔLE → INSTRUCTION → CONTEXTE (faits) → SORTIE JSON` |
| Rédacteur RAG | `src/llm/02_rag_grounded_writer.py` | injecte les phrases de la **vraie fiche** + génère l'annonce |
| Client API | `src/llm/openrouter_client.py` | appel du modèle **Gemma** via OpenRouter |

Choix structurants (cohérents avec le principe « ancré ») :
- **Le génératif ne décide jamais de l'identité** : c'est le retrieval qui identifie ; le VLM
  **vérifie** et le LLM **rédige**. (règle interne R19)
- **Grounding explicite** : le prompt contient *« utilise uniquement le contexte fourni »* +
  les phrases issues de la description **réelle** du produit.
- **Sortie JSON structurée** → on peut valider/parser proprement, et un parseur tolérant gère
  les écarts de format.
- **Dégradation propre** : sans clé API, un rédacteur « mock » prend le relais (l'identif. et
  le prix, locaux, continuent) — la démo ne plante pas.

---

## 4. Résultats (mesurés / observés)

- **Preuve d'ancrage** : sur un produit testé, la mention technique « **Snapdragon 732G** »
  apparaît dans l'annonce générée **parce qu'elle vient de la fiche réelle** (grounding) — pas
  du titre, pas de la « mémoire » du LLM. C'est la démonstration concrète que le texte est
  ancré, pas inventé.
- **Vérificateur visuel** branché : sur une photo iPhone, le validateur renvoie
  `{correspond: vrai, confiance: 1.0, raison: "diagonal dual-camera layout"}` (raison
  factuelle, observable).
- Évaluation RAG tracée dans `reports/07_rag_eval/rag_grounded_eval.json`.
- Tests : `test_llm_rag`, `test_llm_writer`, `test_describe_openrouter`, `test_vlm_validator`.

> 📊 **Chiffres/faits slide** : « le LLM rédige à partir de la fiche réelle (ex. Snapdragon
> 732G vient du grounding) », « VLM validateur : correspondance + raison factuelle ».
> 📸 **Captures** : l'annonce générée à côté de la fiche catalogue (pour montrer que les specs
> correspondent) + le badge de correspondance visuelle dans l'app.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **RAG avec règles d'ancrage explicites + sortie JSON** → exactement les bonnes pratiques.
- ✅ **Séparation des rôles** : retrieval identifie, VLM vérifie, LLM rédige → on supprime la
  principale source d'hallucination (laisser le génératif « deviner »).
- ✅ **Dégradation propre** (mock) → robustesse de démo.

**Limites assumées :**
- **Dépendance à une API externe** (Gemma via OpenRouter) : coût + latence + disponibilité.
  Atténué par le mock, mais c'est une dépendance.
- **Grounding sur la description, pas encore sur les avis** : enrichir avec les *reviews*
  réelles est un gain futur (jointure lazy à faire).
- **Le VLM peut confondre des générations proches** (ex. iPhone 13/14) : c'est mesuré et
  **assumé** ; la facette Akinator + l'humain tranchent. On ne prétend pas à 100 %.
- **Pas de citation passage-par-passage** dans l'annonce (bonne pratique avancée) — possible
  amélioration.

---

## 6. Références
- Prompting Guide — *Retrieval Augmented Generation (RAG) for LLMs* — https://www.promptingguide.ai/research/rag
- Medium (S. Raut) — *How to stop LLM hallucinations in RAG* — https://sharur7.medium.com/how-to-stop-llm-hallucinations-in-retrieval-augmented-generation-rag-5ef2894f9cd6
- arXiv 2407.12858 — *Grounding and evaluation for LLMs (survey)* — https://arxiv.org/pdf/2407.12858
- arXiv 2501.03995 — *RAG-Check: evaluating multimodal RAG* — https://arxiv.org/pdf/2501.03995
- getmaxim.ai — *LLM hallucination detection & mitigation* — https://www.getmaxim.ai/articles/llm-hallucination-detection-and-mitigation-best-techniques/

---

### En une phrase (pour la défense)
*« Nos IA génératives ne devinent jamais : le produit est d'abord retrouvé dans le catalogue,
puis un VLM vérifie visuellement et un LLM rédige uniquement à partir de la fiche réelle
(grounding explicite + sortie JSON). On le prouve : une spec comme "Snapdragon 732G" vient du
contexte fourni, pas de la mémoire du modèle. »*
