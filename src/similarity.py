import ast
import collections
import difflib
import hashlib
import json
import math
import os
import re
import os
import numpy as np
import pickle
import gensim.downloader as api
from gensim.models import Word2Vec
from tqdm import tqdm
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from config import INIT_JSON_PATH

'''
Supports all 3 retrieval modes:
    "tfidf"    – TF-IDF + cosine similarity (baseline)
    "word2vec" – Weighted Word2Vec vectors
    "bert"     – Sentence-BERT embeddings (best semantic quality)
    
For word2vec and bert, we compute *separate* cosine scores for:
        - ambience  (upscale, romantic, casual, …)
        - cuisine   (categories + name)
        - reviews   (what people actually said)
        - practical (price range, noise level, good-for-meal flags)
Then we combine them with configurable weights that default to
prioritising ambience
'''
BERT_CACHE_DIR = os.path.dirname(__file__)


def _bert_cache_key(restaurants: list[dict], field_weights: dict) -> str:
    payload = {
        "business_ids": [r.get("business", {}).get("business_id") for r in restaurants],
        "field_weights": field_weights,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _bert_cache_path(cache_key: str) -> str:
    return os.path.join(BERT_CACHE_DIR, f"bert_cache_{cache_key}.pkl")


def _save_bert_corpus(corpus: dict, cache_key: str):
    """Save BERT corpus to disk, excluding the model itself (too large)."""
    saveable = {
        "model_type":    corpus["model_type"],
        "field_vectors": corpus["field_vectors"], 
        "field_weights": corpus["field_weights"],
        "restaurants":   corpus["restaurants"],
    }
    cache_path = _bert_cache_path(cache_key)
    with open(cache_path, "wb") as f:
        pickle.dump(saveable, f)
    print(f"[similarity] BERT corpus cached to {cache_path}")


def _load_bert_corpus(cache_key: str) -> dict | None:
    """Load cached BERT corpus and reload the model."""
    cache_path = _bert_cache_path(cache_key)
    if not os.path.exists(cache_path):
        return None
    print(f"[similarity] Loading cached BERT corpus from {cache_path}...")
    with open(cache_path, "rb") as f:
        corpus = pickle.load(f)
    from sentence_transformers import SentenceTransformer
    corpus["bert_model"] = SentenceTransformer("all-MiniLM-L6-v2")
    print("[similarity] BERT corpus loaded from cache ✓")
    return corpus

##HELPERS##
 
def parse_ambience(attributes: dict) -> dict:
    raw = attributes.get("Ambience", {})
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except Exception:
            raw = {}
    return raw if isinstance(raw, dict) else {}
 
 
def ambience_text(attributes: dict) -> str:
    terms = [k for k, v in parse_ambience(attributes).items() if v is True]
    return " ".join(terms)

def practical_text(attributes: dict) -> str:
    """
    Build a short document from the business structured attributes. 
    Use RestaurantsPriceRange2, NoiseLevel, GoodForMeal, RestaurantsTakeOut attributes in the json.
    This lets 'quiet cheap lunch' hit a meaningful field vector.
    """
    if not attributes:
        return ""
    tokens = []
    price = attributes.get("RestaurantsPriceRange2")
    if price:
        try:
            p = int(str(price).strip())
            tokens += ["cheap"] * max(0, 3 - p)    
            tokens += ["expensive"] * max(0, p - 2)   
        except ValueError:
            pass
        
    #noise tags, e.g. "quiet quiet" for quiet places, "loud loud" for loud places, "loud loud loud" for very_loud places (nothing for avg)
    noise = attributes.get("NoiseLevel", "")
    if "quiet" in str(noise).lower():
        tokens += ["quiet", "quiet"]
    elif "loud" in str(noise).lower():
        tokens += ["loud", "loud"]
    elif "very_loud" in str(noise).lower():
        tokens += ["loud", "loud", "loud"]
 
    #good-for-meal tags, e.g. "lunch", "dinner", "breakfast"
    good_for = attributes.get("GoodForMeal", {})
    if isinstance(good_for, str):
        try:
            good_for = ast.literal_eval(good_for)
        except Exception:
            good_for = {}
    if isinstance(good_for, dict):
        for meal, flag in good_for.items():
            if flag is True:
                tokens.append(meal)   
                
    #takeout/delivery tags            
    if str(attributes.get("RestaurantsTakeOut", "")).lower() == "true":
        tokens.append("takeout")
    if str(attributes.get("RestaurantsDelivery", "")).lower() == "true":
        tokens.append("delivery")
        
    #alcohol tags, e.g. "bar", "cocktails", "drinks" for full_bar, "beer", "wine", "drinks" for beer_and_wine
    alcohol = attributes.get("Alcohol", "")
    if "full_bar" in str(alcohol).lower():
        tokens += ["bar", "cocktails", "drinks"]
    if "beer_and_wine" in str(alcohol).lower():
        tokens += ["beer", "wine", "drinks"]
 
    return " ".join(tokens)


def extract_fields(restaurant: dict) -> dict:
    """
    Return the four field strings used for both vectorization and late fusion.
    """
    biz = restaurant.get("business", {})
    attrs = biz.get("attributes") or {}
 
    return {
        "ambience":  ambience_text(attrs),
        "cuisine":   f"{biz.get('name', '')} {biz.get('categories', '')}",
        "reviews":   restaurant.get("combined_reviews", ""),
        "practical": practical_text(attrs),
    }

##CORPUS BUILDING##

DEFAULT_FIELD_WEIGHTS = {
    "ambience":  0.35,
    "cuisine":   0.30,
    "reviews":   0.20,
    "practical": 0.15,
}

def build_corpus(restaurants: list[dict], model_type: str = "word2vec", field_weights: dict | None = None, svd_n_components: int = 100) -> dict:
    weights = {**DEFAULT_FIELD_WEIGHTS, **(field_weights or {})}
 
    if model_type in ("tfidf+svd", "tfidf", "svd"): 
        return _build_tfidf_svd_corpus(restaurants, n_components=svd_n_components)
    elif model_type == "word2vec":
        return _build_word2vec_corpus(restaurants, weights)
    elif model_type == "bert":
        return _build_bert_corpus(restaurants, weights)
    elif model_type == "bert+svd":
        return _build_bert_svd_corpus(restaurants, weights, n_components=svd_n_components)
    else:
        raise ValueError(f"Unknown model_type '{model_type}'. Choose tfidf | word2vec | bert.")
    
# TF-IDF corpus
def _build_tfidf_svd_corpus(restaurants: list[dict], n_components: int = 100) -> dict:
    documents = []
    for r in restaurants:
        fields = extract_fields(r)
        # Ambience repeated 3× so it has more mass in the TF-IDF doc
        documents.append(
            f"{fields['cuisine']} "
            f"{fields['ambience']} {fields['ambience']} {fields['ambience']} "
            f"{fields['reviews']} "
            f"{fields['practical']}"
        )
 
    vectorizer = TfidfVectorizer(
        stop_words="english",
        sublinear_tf=True,
        min_df=2,
        ngram_range=(1, 2),
    )
    tfidf_matrix = vectorizer.fit_transform(documents)
    
    max_k = min(tfidf_matrix.shape) - 1
    n_components = min(n_components, max_k)

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    doc_vectors = svd.fit_transform(tfidf_matrix)        # (N, k)

    print(f"[similarity] TF-IDF+SVD ready — {n_components} dims, "
          f"variance explained: {svd.explained_variance_ratio_.sum():.1%}")
 
    return {
        "model_type":  "tfidf+svd",
        "vectorizer":  vectorizer,
        "svd":         svd,          
        "doc_vectors": doc_vectors,
        "restaurants": restaurants,
    }
 # Word2Vec corpus  (late-fusion field vectors)
 
def _build_word2vec_corpus(restaurants, field_weights):
    print("[similarity] Loading GloVe model...")
    w2v_model = api.load("glove-wiki-gigaword-100")

    all_fields = [extract_fields(r) for r in restaurants]

    all_docs = [
        f"{f['cuisine']} {f['ambience']} {f['reviews']} {f['practical']}"
        for f in all_fields
    ]
    tfidf_vec = TfidfVectorizer(
        stop_words="english", sublinear_tf=True, min_df=2,
        ngram_range=(1, 2), lowercase=True,
    )
    tfidf_vec.fit(all_docs)

    # Build vocab embedding matrix ONCE (vocab_size, 100)
    print("[similarity] Building vocab embedding matrix...")
    vocab = tfidf_vec.get_feature_names_out()
    vocab_vectors = np.zeros((len(vocab), w2v_model.vector_size))
    for i, word in enumerate(vocab):
        if word in w2v_model:
            vocab_vectors[i] = w2v_model[word]

    field_vectors = {}
    for field_name in DEFAULT_FIELD_WEIGHTS:
        print(f"[similarity] Encoding field '{field_name}'...")
        texts = [f[field_name] for f in all_fields]

        # (N, vocab_size) — one call, no loop
        tfidf_matrix = tfidf_vec.transform(texts).toarray()

        # (N, vocab_size) @ (vocab_size, 100) = (N, 100) — one matrix multiply
        weighted = tfidf_matrix @ vocab_vectors

        # Normalize by weight sums to get weighted average
        weight_sums = tfidf_matrix.sum(axis=1, keepdims=True)
        weight_sums[weight_sums == 0] = 1
        field_vectors[field_name] = weighted / weight_sums

    return {
        "model_type": "word2vec",
        "w2v_model": w2v_model,
        "tfidf_vec": tfidf_vec,
        "field_vectors": field_vectors,
        "field_weights": field_weights,
        "restaurants": restaurants,
    }
 
 
def _compute_w2v_vector(tokens: list[str], w2v_model, tfidf_vectorizer: TfidfVectorizer, tfidf_weights: np.ndarray) -> np.ndarray:
    """
    Weighted average of Word2Vec token vectors.
    Weight = TF-IDF score for that token (falls back to 0.1 if not in vocab).
    """
    vocab = tfidf_vectorizer.get_feature_names_out()
    token_to_weight = {vocab[i]: w for i, w in enumerate(tfidf_weights) if w > 0}
 
    vectors, weights = [], []
    for token in tokens:
        if token in w2v_model:
            vectors.append(w2v_model[token])
            weights.append(token_to_weight.get(token, 0.1))
 
    if not vectors:
        return np.zeros(w2v_model.vector_size)
 
    vectors = np.array(vectors)
    weights = np.array(weights)
    weights /= weights.sum()
    return np.average(vectors, axis=0, weights=weights)
 
 
# BERT corpus
 
def _build_bert_corpus(restaurants: list[dict], field_weights: dict) -> dict:
    from sentence_transformers import SentenceTransformer

    cache_key = _bert_cache_key(restaurants, field_weights)
    cached = _load_bert_corpus(cache_key)
    if cached is not None:
        return cached
 
    print("[similarity] Loading BERT model (all-MiniLM-L6-v2)…")
    bert_model = SentenceTransformer("all-MiniLM-L6-v2")
 
    all_fields = [extract_fields(r) for r in restaurants]
 
    field_vectors = {}
    for field_name in DEFAULT_FIELD_WEIGHTS:
        texts = [f[field_name] if f[field_name].strip() else "none" for f in all_fields]
        print(f"[similarity] Encoding field '{field_name}' ({len(texts)} docs)…")
        field_vectors[field_name] = bert_model.encode(
            texts,
            batch_size=64,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
 
    corpus = {
        "model_type":    "bert",
        "bert_model":    bert_model,
        "field_vectors": field_vectors,
        "field_weights": field_weights,
        "restaurants":   restaurants,
    }
    _save_bert_corpus(corpus, cache_key)
    return corpus

    
# Query vectorization
 
def vectorize_query_tfidf_svd(query: str, corpus: dict) -> np.ndarray:
    """
    Project query into the same SVD latent space as the documents.
    query string → TF-IDF sparse vector (1, V) → SVD projection (k,)
    """
    tfidf_vec = corpus["vectorizer"].transform([query]) 
    return corpus["svd"].transform(tfidf_vec)[0]
 
 
def vectorize_query_w2v(query: str, corpus: dict) -> np.ndarray:
    """
    For late-fusion Word2Vec, we encode the query once and compare it
    against each field's restaurant vectors separately.
    The query is treated as a single 'document' — no field splitting needed
    because the user's query is already a short mixed-intent string.
    """
    tokens = re.findall(r'\b\w+\b', query.lower())
    tfidf_weights = corpus["tfidf_vec"].transform([query.lower()]).toarray().flatten()
    return _compute_w2v_vector(tokens, corpus["w2v_model"], corpus["tfidf_vec"], tfidf_weights)
 
 
def vectorize_query_bert(query: str, corpus: dict) -> np.ndarray:
    return corpus["bert_model"].encode([query], convert_to_numpy=True)[0]

def fuse_scores(query_vec: np.ndarray, corpus: dict) -> np.ndarray:
    """
    Compute a weighted average of per-field cosine similarities.
 
    For each field (ambience, cuisine, reviews, practical):
        field_score[i] = cosine_sim(query_vec, restaurant_field_vec[i])
    
    Final score = Σ weight_f * field_score_f  for all fields f
 
    This means a query like 'quiet cheap lunch' will score high on the
    practical field even if the restaurant's review text uses different
    vocabulary, because those signals are kept separate and not diluted.
    """
    q = query_vec.reshape(1, -1)
    weights = corpus["field_weights"]
    field_vectors = corpus["field_vectors"]
 
    combined = np.zeros(len(corpus["restaurants"]))
    for field_name, weight in weights.items():
        field_mat = field_vectors[field_name]  # (N, D)
        # Some restaurants may have zero-vectors for sparse fields (e.g. no ambience tags)
        # sklearn cosine handles this gracefully (returns 0)
        sims = sklearn_cosine(q, field_mat).flatten()
        combined += weight * sims
 
    return combined


def rank_restaurants(query: str, corpus: dict, type: str = "word2vec") -> list[dict]:
    if type in ("tfidf", "tfidf+svd", "svd"):
        query = _correct_query(query, corpus["vectorizer"])
    elif type == "word2vec":
        query = _correct_query(query, corpus["tfidf_vec"])
    if type in ("tfidf", "tfidf+svd", "svd"):
        query_vec = vectorize_query_tfidf_svd(query, corpus)
        scores = sklearn_cosine(
            query_vec.reshape(1, -1), corpus["doc_vectors"]
        ).flatten()
    elif type == "word2vec":
        query_vec = vectorize_query_w2v(query, corpus)
        scores = fuse_scores(query_vec, corpus)
    elif type == "bert":
        query_vec = vectorize_query_bert(query, corpus)
        scores = fuse_scores(query_vec, corpus)
    else:
        raise ValueError(f"Unknown type '{type}'. Choose tfidf, word2vec, or bert.")
    
    results = []
    for idx, score in enumerate(scores):
        if score > 0:
            r = corpus["restaurants"][idx]
            results.append({
                "score":            round(float(score), 6),
                "business":         r["business"],
                "reviews":          r.get("reviews", []),
                "combined_reviews": r.get("combined_reviews", ""),
            })
 
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# used ChatGPT to help debug this function when it stopped working after adding SVD
def _correct_query(query: str, vectorizer) -> str:
    """
    Replace words not in the TF-IDF vocabulary with their closest match.
    Words already in the vocabulary pass through unchanged.
    Words with no close match (cutoff=0.6) are kept as-is.
    """
    vocab = list(vectorizer.vocabulary_.keys())
    corrected = []
    for word in re.findall(r'\b\w+\b', query.lower()):
        if word in vectorizer.vocabulary_:
            corrected.append(word)
        else:
            matches = difflib.get_close_matches(word, vocab, n=1, cutoff=0.75)
            corrected.append(matches[0] if matches else word)
    return " ".join(corrected)


def get_similarity_scores(query: str, restaurants: list[dict], type: str = "word2vec", field_weights: dict | None = None,) -> list[float]:  
    """
    Convenience function for search.py.
    Given a query and a list of restaurant dicts (already filtered by city),
    returns a flat list of cosine similarity scores in the same order as the input.
 
    Args:
        query: user query e.g. "ramen" or "spicy tacos"
        restaurants: city-filtered list of restaurant dicts from init.json
        type: either "word2vec" or "tfidf"

    Returns:
        List of float scores, one per restaurant, in the original order.
        Scores are 0.0 for restaurants with no term overlap with the query.
    """
    if not restaurants:
        return []
    
    corpus = build_corpus(restaurants, model_type=type, field_weights=field_weights)    
    if type == "tfidf":
        corrected_query = _correct_query(query, corpus["vectorizer"])
    else:
        corrected_query = query
 
    if type in ("tfidf", "tfidf+svd", "svd"):
        corrected_query = _correct_query(query, corpus["vectorizer"])
        query_vec = vectorize_query_tfidf_svd(corrected_query, corpus)
        scores = sklearn_cosine(
            query_vec.reshape(1, -1), corpus["doc_vectors"]
        ).flatten()
    elif type == "word2vec":
        query_vec = vectorize_query_w2v(corrected_query, corpus)
        scores = fuse_scores(query_vec, corpus)
    elif type == "bert":
        query_vec = vectorize_query_bert(corrected_query, corpus)
        scores = fuse_scores(query_vec, corpus)
    else:
        raise ValueError(f"Unknown type '{type}'. Choose tfidf, word2vec, or bert.")
    
    return [round(float(s), 6) for s in scores]

def explain_svd_result(
    query: str,
    restaurant: dict,
    corpus: dict,
    top_n_dims: int = 5,
    top_n_terms: int = 8,
) -> dict:
    """
    For each top-contributing SVD dimension, show:
      - how much the query activates it
      - how much the restaurant activates it
      - the top positive and negative terms defining that dimension
    This is the per-result explainability your professor requires.
    """
    assert corpus["model_type"] in ("tfidf+svd", "svd"), \
        "explain_svd_result() requires a tfidf+svd corpus"

    svd        = corpus["svd"]
    vectorizer = corpus["vectorizer"]
    restaurants = corpus["restaurants"]
    doc_vectors = corpus["doc_vectors"]   # (N, k)

    biz_id = restaurant["business"]["business_id"]
    rest_idx = next(
        (i for i, r in enumerate(restaurants)
         if r["business"]["business_id"] == biz_id),
        None,
    )
    if rest_idx is None:
        return {"error": "Restaurant not found in corpus"}

    query_vec = vectorize_query_tfidf_svd(query, corpus)   # (k,)
    rest_vec  = doc_vectors[rest_idx]                       # (k,)

    # Per-dimension contribution to the cosine similarity
    contributions = query_vec * rest_vec
    q_norm = np.linalg.norm(query_vec)
    r_norm = np.linalg.norm(rest_vec)
    norm_contributions = contributions / (q_norm * r_norm) if q_norm > 0 and r_norm > 0 else contributions

    top_dim_indices = np.argsort(np.abs(norm_contributions))[::-1][:top_n_dims]
    Vt    = svd.components_                        # (k, V)
    terms = vectorizer.get_feature_names_out()     # (V,)

    top_dimensions = []
    for dim_idx in top_dim_indices:
        loadings    = Vt[dim_idx]
        pos_terms   = [terms[i] for i in np.argsort(loadings)[::-1][:top_n_terms]]
        neg_terms   = [terms[i] for i in np.argsort(loadings)[:top_n_terms]]
        contribution = float(norm_contributions[dim_idx])

        top_dimensions.append({
            "dim_index":             int(dim_idx),
            "query_activation":      round(float(query_vec[dim_idx]), 4),
            "restaurant_activation": round(float(rest_vec[dim_idx]), 4),
            "contribution":          round(contribution, 4),
            "direction":             "positive" if contribution >= 0 else "negative",
            "top_positive_terms":    pos_terms,
            "top_negative_terms":    neg_terms,
            "dimension_label":       " / ".join(pos_terms[:3]),
        })

    return {
        "restaurant_name":   restaurant["business"]["name"],
        "overall_score":     round(float(norm_contributions.sum()), 4),
        "query_coords":      query_vec.tolist(),
        "restaurant_coords": rest_vec.tolist(),
        "top_dimensions":    top_dimensions,
    }


def _ensure_svd_biz_index(corpus: dict) -> dict:
    idx = corpus.get("_svd_biz_id_to_index")
    if isinstance(idx, dict):
        return idx

    restaurants = corpus.get("restaurants") or []
    idx = {}
    for i, r in enumerate(restaurants):
        biz = r.get("business", {})
        biz_id = biz.get("business_id")
        if biz_id:
            idx[biz_id] = i
    corpus["_svd_biz_id_to_index"] = idx
    return idx


def _svd_dimension_descriptor(corpus: dict, dim_idx: int, top_n_terms: int = 8) -> dict:
    cache = corpus.setdefault("_svd_dim_cache", {})
    key = (int(dim_idx), int(top_n_terms))
    if key in cache:
        return cache[key]

    svd = corpus["svd"]
    vectorizer = corpus["vectorizer"]
    Vt = svd.components_
    terms = vectorizer.get_feature_names_out()

    loadings = Vt[dim_idx]
    pos_terms = [terms[i] for i in np.argsort(loadings)[::-1][:top_n_terms]]
    neg_terms = [terms[i] for i in np.argsort(loadings)[:top_n_terms]]

    desc = {
        "dim_index": int(dim_idx),
        "dimension_label": " / ".join(pos_terms[:3]),
        "top_positive_terms": pos_terms,
        "top_negative_terms": neg_terms,
    }
    cache[key] = desc
    return desc


_GENERIC_THEME_TERMS = {
    "food",
    "foods",
    "good",
    "great",
    "best",
    "nice",
    "new",
    "old",
    "place",
    "places",
    "restaurant",
    "restaurants",
    "service",
    "menu",
    "order",
    "ordered",
    "love",
    "loved",
    "like",
    "staff",
    "really",
    "definitely",
    "also",
    "one",
    "two",
    "time",
}


def _is_generic_theme_term(term: str) -> bool:
    t = (term or "").lower().strip()
    if not t:
        return True
    # Handle ngrams like "coffee shop", only treat as generic if every token is generic.
    tokens = re.split(r"[^a-z0-9]+", t)
    tokens = [tok for tok in tokens if tok]
    if not tokens:
        return True
    return all(tok in _GENERIC_THEME_TERMS for tok in tokens)


def _dimension_side_terms(desc: dict, side: int) -> list[str]:
    if side >= 0:
        return list(desc.get("top_positive_terms") or [])
    return list(desc.get("top_negative_terms") or [])


def _dimension_display_terms(desc: dict, side: int, max_terms: int = 8) -> list[str]:
    raw = _dimension_side_terms(desc, side)[:max_terms]
    filtered = [t for t in raw if not _is_generic_theme_term(t)]
    return filtered if filtered else raw


def _dimension_display_label(desc: dict, side: int, n_terms: int = 3) -> str:
    terms = _dimension_display_terms(desc, side)
    picked = [t for t in terms if t][:n_terms]
    return " / ".join(picked) if picked else (desc.get("dimension_label") or "")


def prepare_query_tfidf_svd(query: str, corpus: dict) -> dict:
    """
    Precompute corrected query text and its SVD coordinates once per request.
    """
    assert corpus["model_type"] in ("tfidf+svd", "svd"), \
        "prepare_query_tfidf_svd() requires a tfidf+svd corpus"

    corrected_query = _correct_query(query, corpus["vectorizer"])
    query_vec = vectorize_query_tfidf_svd(corrected_query, corpus)
    return {
        "corrected_query": corrected_query,
        "query_vec": query_vec,
    }


def get_query_latent_dimensions(
    prepared_query: dict,
    corpus: dict,
    top_n_dims: int = 5,
    top_n_terms: int = 8,
) -> dict:
    """
    Returns the top latent dimensions activated by a query, reusing a
    precomputed query vector.
    """
    assert corpus["model_type"] in ("tfidf+svd", "svd"), \
        "get_query_latent_dimensions() requires a tfidf+svd corpus"

    corrected_query = prepared_query["corrected_query"]
    query_vec = prepared_query["query_vec"]
    sorted_dim_indices = [int(i) for i in np.argsort(np.abs(query_vec))[::-1]]

    dims = []
    for dim_idx in sorted_dim_indices:
        if len(dims) >= top_n_dims:
            break
        activation = float(query_vec[dim_idx])
        side = 1 if activation >= 0 else -1
        desc = _svd_dimension_descriptor(corpus, dim_idx, top_n_terms=top_n_terms)
        display_terms = _dimension_display_terms(desc, side)
        # Filter out dimensions that are too generic/noisy after filtering.
        if not any(not _is_generic_theme_term(t) for t in display_terms[:3]):
            continue

        dims.append({
            **desc,
            "query_activation": round(activation, 4),
            "display_side": "positive" if side >= 0 else "negative",
            "display_terms": display_terms[:top_n_terms],
            "display_label": _dimension_display_label(desc, side, n_terms=3),
        })

    return {
        "corrected_query": corrected_query,
        "top_dimensions": dims,
    }
def get_result_latent_dimensions(
    prepared_query: dict,
    business_id: str,
    corpus: dict,
    top_n_pos: int = 3,
    top_n_neg: int = 3,
    top_n_terms: int = 8,
) -> dict:
    """
    Returns the top positive and negative latent dimensions for a specific
    (query, restaurant) pair, reusing a precomputed query vector.
    """
    assert corpus["model_type"] in ("tfidf+svd", "svd"), \
        "get_result_latent_dimensions() requires a tfidf+svd corpus"

    corrected_query = prepared_query["corrected_query"]
    query_vec = prepared_query["query_vec"]

    rest_idx = _ensure_svd_biz_index(corpus).get(business_id)
    if rest_idx is None:
        return {"error": "Restaurant not found in corpus"}

    rest_vec = corpus["doc_vectors"][rest_idx]

    contributions = query_vec * rest_vec
    q_norm = np.linalg.norm(query_vec)
    r_norm = np.linalg.norm(rest_vec)
    norm_contributions = contributions / (q_norm * r_norm) if q_norm > 0 and r_norm > 0 else contributions

    sorted_pos = [int(i) for i in np.argsort(norm_contributions)[::-1] if norm_contributions[int(i)] > 0]
    sorted_neg = [int(i) for i in np.argsort(norm_contributions) if norm_contributions[int(i)] < 0]

    def build_dim(dim_idx: int, display_side: int) -> dict:
        desc = _svd_dimension_descriptor(corpus, dim_idx, top_n_terms=top_n_terms)
        return {
            **desc,
            "query_activation": round(float(query_vec[dim_idx]), 4),
            "restaurant_activation": round(float(rest_vec[dim_idx]), 4),
            "contribution": round(float(norm_contributions[dim_idx]), 4),
            "display_side": "positive" if display_side >= 0 else "negative",
            "display_terms": _dimension_display_terms(desc, display_side)[:top_n_terms],
            "display_label": _dimension_display_label(desc, display_side, n_terms=3),
        }

    positive_dimensions = []
    for dim_idx in sorted_pos:
        if len(positive_dimensions) >= top_n_pos:
            break
        side = 1 if float(query_vec[dim_idx]) >= 0 else -1
        desc = _svd_dimension_descriptor(corpus, dim_idx, top_n_terms=top_n_terms)
        display_terms = _dimension_display_terms(desc, side)
        if not any(not _is_generic_theme_term(t) for t in display_terms[:3]):
            continue
        positive_dimensions.append(build_dim(dim_idx, side))

    negative_dimensions = []
    for dim_idx in sorted_neg:
        if len(negative_dimensions) >= top_n_neg:
            break
        # For mismatches, show the restaurant's side (what the restaurant leans toward).
        side = 1 if float(rest_vec[dim_idx]) >= 0 else -1
        desc = _svd_dimension_descriptor(corpus, dim_idx, top_n_terms=top_n_terms)
        display_terms = _dimension_display_terms(desc, side)
        if not any(not _is_generic_theme_term(t) for t in display_terms[:3]):
            continue
        negative_dimensions.append(build_dim(dim_idx, side))

    return {
        "corrected_query": corrected_query,
        "overall_score": round(float(norm_contributions.sum()), 4),
        "positive_dimensions": positive_dimensions,
        "negative_dimensions": negative_dimensions,
    }


def describe_svd_dimensions(corpus: dict, n_dims: int = 10, n_terms: int = 10) -> list[dict]:
    """
    Returns a description of each latent dimension — use this for your
    writeup section 'discuss what the latent dimensions you discover are'.
    """
    assert corpus["model_type"] in ("tfidf+svd", "svd"), \
        "describe_svd_dimensions() requires a tfidf+svd corpus"

    svd   = corpus["svd"]
    terms = corpus["vectorizer"].get_feature_names_out()
    Vt    = svd.components_   # (k, V)

    results = []
    for dim_idx in range(min(n_dims, Vt.shape[0])):
        loadings = Vt[dim_idx]
        results.append({
            "dim_index":          dim_idx,
            "singular_value":     round(float(svd.singular_values_[dim_idx]), 3),
            "variance_explained": round(float(svd.explained_variance_ratio_[dim_idx]), 4),
            "top_positive_terms": [terms[i] for i in np.argsort(loadings)[::-1][:n_terms]],
            "top_negative_terms": [terms[i] for i in np.argsort(loadings)[:n_terms]],
        })
    return results
 
 
if __name__ == "__main__":
    import json

    with open(os.path.join(os.path.dirname(__file__), "init.json"), "r", encoding="utf-8") as f:
        all_restaurants = json.load(f)
    
    city = "Philadelphia"
    test_queries = [
        "casual takeout sushi",
        "fancy formal sushi",
        "fancy formal japanese food",
        "romantic dinner",
        "authentic vietnamese",
        "quiet cheap lunch",
    ]
    
    city_restaurants = [
        r for r in all_restaurants
        if r["business"].get("city", "").lower().strip() == city.lower()
    ]

    print(f"✓ Loaded {len(city_restaurants)} restaurants in {city}\n")
    print("=" * 100)
    print("Building corpuses")
    print("=" * 100)

    tfidf_corpus = build_corpus(city_restaurants, model_type="tfidf")
    # word2vec_corpus = build_corpus(city_restaurants, model_type="word2vec")
    bert_corpus = build_corpus(city_restaurants, model_type="bert")

    print("\n" + "=" * 100)
    print("COMPARISON: SVD+TF-IDF vs Word2Vec vs BERT")
    print("=" * 100)
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        print("-" * 100)
        
        # TF-IDF results
        tfidf_results = rank_restaurants(query, tfidf_corpus, type="tfidf")
        print("TF-IDF Top 5:")
        for i, r in enumerate(tfidf_results[:5], 1):
            biz = r["business"]
            print(f"  {i}. [{r['score']:.4f}] {biz['name']} | {biz.get('categories', '')[:50]}")
        
        # # Word2Vec results
        # w2v_results = rank_restaurants(query, word2vec_corpus, type="word2vec")
        # print("\nWord2Vec Top 5:")
        # for i, r in enumerate(w2v_results[:5], 1):
        #     biz = r["business"]
        #     print(f"  {i}. [{r['score']:.4f}] {biz['name']} | {biz.get('categories', '')[:50]}")
        
        # BERT results
        bert_results = rank_restaurants(query, bert_corpus, type="bert")
        print("\nBERT Top 5:")
        for i, r in enumerate(bert_results[:5], 1):
            biz = r["business"]
            print(f"  {i}. [{r['score']:.4f}] {biz['name']} | {biz.get('categories', '')[:50]}")
        
        # Show overlap
        # tfidf_names = set(r["business"]["name"] for r in tfidf_results[:5])
        # w2v_names = set(r["business"]["name"] for r in w2v_results[:5])
        # bert_names = set(r["business"]["name"] for r in bert_results[:5])
        
        # tfidf_w2v_overlap = len(tfidf_names & w2v_names)
        # tfidf_bert_overlap = len(tfidf_names & bert_names)
        # w2v_bert_overlap = len(w2v_names & bert_names)
        
        # print(f"\n📊 Top-5 Overlap: TF-IDF↔W2V={tfidf_w2v_overlap}, TF-IDF↔BERT={tfidf_bert_overlap}, W2V↔BERT={w2v_bert_overlap}")
        print()
   
