import ast
import json

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine


def extract_ambience_terms(biz: dict) -> str:
    """
    Extract ambience-related terms from business attributes.

    Handles cases where Ambience is already a dict or is stored as a string.
    Repeats ambience terms to make them slightly more influential in TF-IDF.
    """
    attributes = biz.get("attributes", {}) or {}
    ambience_raw = attributes.get("Ambience", {})

    if isinstance(ambience_raw, str):
        try:
            ambience_raw = ast.literal_eval(ambience_raw)
        except Exception:
            ambience_raw = {}

    if not isinstance(ambience_raw, dict):
        return ""

    ambience_terms = [k for k, v in ambience_raw.items() if v is True]
    return " ".join(ambience_terms * 3)


def build_tfidf_corpus(restaurants: list[dict]) -> dict:
    """
    Pre-compute TF-IDF matrix for all restaurants.
    Call this once when the app starts (e.g. after loading init.json).

    Each restaurant's document includes:
    - business name
    - categories
    - combined_reviews
    - ambience tags

    Returns a corpus dict to pass into rank_restaurants().
    """
    documents = []

    for r in restaurants:
        biz = r.get("business", {})
        name = biz.get("name", "")
        categories = biz.get("categories", "")
        reviews = r.get("combined_reviews", "")
        ambience_str = extract_ambience_terms(biz)

        documents.append(f"{name} {categories} {reviews} {ambience_str}")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        sublinear_tf=True,
        min_df=2,
        ngram_range=(1, 2),
    )

    tfidf_matrix = vectorizer.fit_transform(documents)

    return {
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "restaurants": restaurants,
    }


def vectorize_query(query: str, vectorizer: TfidfVectorizer):
    """
    Transform a raw user query string into a TF-IDF vector using the
    already-fitted vectorizer from the corpus.

    Unknown terms are silently ignored by sklearn.
    """
    return vectorizer.transform([query])


def rank_restaurants(query: str, corpus: dict) -> list[dict]:
    """
    Score every restaurant against the query and return them sorted by
    descending cosine similarity.

    Args:
        query: raw user query string e.g. "casual ramen New York"
        corpus: dict returned by build_tfidf_corpus()

    Returns:
        List of result dicts sorted best-first:
        [
          {
            "score": 0.312,
            "business": { ... },
            "combined_reviews": "..."
          },
          ...
        ]
    """
    query_vec = vectorize_query(query, corpus["vectorizer"])
    scores = sklearn_cosine(query_vec, corpus["tfidf_matrix"]).flatten()

    results = []
    for idx, score in enumerate(scores):
        if score > 0:
            restaurant = corpus["restaurants"][idx]
            results.append({
                "score": round(float(score), 6),
                "business": restaurant.get("business", {}),
                "combined_reviews": restaurant.get("combined_reviews", ""),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_similarity_scores(query: str, restaurants: list[dict]) -> list[float]:
    """
    Convenience function for search.py.
    Given a query and a list of restaurant dicts (already filtered by city),
    returns a flat list of cosine similarity scores in the same order as the input.

    Args:
        query: user query e.g. "ramen" or "spicy tacos"
        restaurants: city-filtered list of restaurant dicts from init.json

    Returns:
        List of float scores, one per restaurant, in the original order.
        Scores are 0.0 for restaurants with no term overlap with the query.
    """
    if not restaurants:
        return []

    corpus = build_tfidf_corpus(restaurants)
    query_vec = vectorize_query(query, corpus["vectorizer"])
    scores = sklearn_cosine(query_vec, corpus["tfidf_matrix"]).flatten()
    return [round(float(s), 6) for s in scores]


if __name__ == "__main__":
    with open("src/init.json", "r", encoding="utf-8") as f:
        restaurants = json.load(f)

    print("Loaded restaurants:", len(restaurants))

    corpus = build_tfidf_corpus(restaurants)

    test_queries = ["ramen", "sushi", "cheesesteak", "casual dinner", "romantic italian"]

    for q in test_queries:
        ranked = rank_restaurants(q, corpus)
        print(f"\nQuery: '{q}'")
        for r in ranked[:5]:
            print(f"  {r['score']:.4f}  {r['business'].get('name', 'Unknown')}")
 
# if __name__ == "__main__":
#     sample_restaurants = [
#         {
#             "business": {"business_id": "1", "name": "Tokyo Ramen House",
#                          "categories": "Restaurants, Ramen, Japanese"},
#             "reviews": [],
#             "combined_reviews": "rich broth noodles pork belly soft boiled egg tonkotsu ramen amazing"
#         },
#         {
#             "business": {"business_id": "2", "name": "Philly Cheesesteak Co",
#                          "categories": "Restaurants, Cheesesteaks, American"},
#             "reviews": [],
#             "combined_reviews": "classic cheesesteak whiz onions fresh roll best philly cheese steak ever"
#         },
#         {
#             "business": {"business_id": "3", "name": "Sushi Garden",
#                          "categories": "Restaurants, Sushi, Japanese"},
#             "reviews": [],
#             "combined_reviews": "fresh fish nigiri sashimi rolls rice vinegar soy wasabi miso soup"
#         },
#         {
#             "business": {"business_id": "4", "name": "Ramen Republic",
#                          "categories": "Restaurants, Ramen, Noodles"},
#             "reviews": [],
#             "combined_reviews": "spicy miso ramen thick noodles corn butter rich pork broth chashu"
#         },
#     ]
 
#     corpus = build_tfidf_corpus(sample_restaurants)
 
#     for q in ["ramen", "cheesesteak philly", "japanese sushi"]:
#         ranked = rank_restaurants(q, corpus)
#         print(f"\nQuery: '{q}'")
#         for r in ranked:
#             print(f"  {r['score']:.4f}  {r['business']['name']}")


 