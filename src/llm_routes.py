"""
LLM routes:
  - POST /api/explain  — always registered, returns a 1-2 sentence LLM justification
                         for why a retrieved restaurant matches the user query.
  - POST /api/chat     — only loaded when USE_LLM = True in routes.py (legacy RAG chat).

Setup:
  1. Add SPARK_API_KEY=your_key to .env
  2. Optional Set USE_LLM = True in routes.py to enable the chat endpoint
"""
import json
import logging
import os
import re

from flask import Response, jsonify, request, stream_with_context
from infosci_spark_client import LLMClient

logger = logging.getLogger(__name__)


def llm_search_decision(client, user_message):
    """Ask the LLM whether to search the DB and which word to use."""
    messages = [
        {
            "role": "system",
            "content": (
                "You have access to a database of Keeping Up with the Kardashians episode titles, "
                "descriptions, and IMDB ratings. Search is by a single word in the episode title. "
                "Reply with exactly: YES followed by one space and ONE word to search (e.g. YES wedding), "
                "or NO if the question does not need episode data."
            ),
        },
        {"role": "user", "content": user_message},
    ]
    response = client.chat(messages)
    content = (response.get("content") or "").strip().upper()
    logger.info(f"LLM search decision: {content}")
    if re.search(r"\bNO\b", content) and not re.search(r"\bYES\b", content):
        return False, None
    yes_match = re.search(r"\bYES\s+(\w+)", content)
    if yes_match:
        return True, yes_match.group(1).lower()
    if re.search(r"\bYES\b", content):
        return True, "Kardashian"
    return False, None


def register_chat_route(app, json_search):
    """Register the /api/chat SSE endpoint. Called from routes.py."""

    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        api_key = os.getenv("API_KEY")
        if not api_key:
            return jsonify({"error": "API_KEY not set — add it to your .env file"}), 500

        client = LLMClient(api_key=api_key)
        use_search, search_term = llm_search_decision(client, user_message)

        if use_search:
            episodes = json_search(search_term or "Kardashian")
            context_text = "\n\n---\n\n".join(
                f"Title: {ep['title']}\nDescription: {ep['descr']}\nIMDB Rating: {ep['imdb_rating']}"
                for ep in episodes
            ) or "No matching episodes found."
            messages = [
                {"role": "system", "content": "Answer questions about Keeping Up with the Kardashians using only the episode information provided."},
                {"role": "user", "content": f"Episode information:\n\n{context_text}\n\nUser question: {user_message}"},
            ]
        else:
            messages = [
                {"role": "system", "content": "You are a helpful assistant for Keeping Up with the Kardashians questions."},
                {"role": "user", "content": user_message},
            ]

        def generate():
            if use_search and search_term:
                yield f"data: {json.dumps({'search_term': search_term})}\n\n"
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


# Debugged with limited help of GenAI, fixing prompt errors
def register_explain_route(app):
    """Register POST /api/explain — on-demand LLM justification for a single restaurant result."""
    import ast

    from search import load_processed_data

    @app.route("/api/explain", methods=["POST"])
    def explain():
        data = request.get_json() or {}
        business_id = (data.get("business_id") or "").strip()
        query = (data.get("query") or "").strip()

        if not business_id or not query:
            return jsonify({"error": "business_id and query are required", "explanation": None}), 400

        api_key = os.getenv("SPARK_API_KEY")
        if not api_key:
            return jsonify({"error": "SPARK_API_KEY not configured", "explanation": None}), 500

        processed_data = load_processed_data()
        if processed_data is None:
            return jsonify({"error": "Restaurant data unavailable", "explanation": None}), 500

        # Find the restaurant entry by business_id
        entry = next((r for r in processed_data if r["business"].get("business_id") == business_id), None)
        if entry is None:
            return jsonify({"error": "Restaurant not found", "explanation": None}), 404

        business = entry["business"]
        reviews_text = (entry.get("combined_reviews") or "").strip()

        # Parse ambience
        ambience_raw = (business.get("attributes") or {}).get("Ambience") or {}
        if isinstance(ambience_raw, str):
            try:
                ambience_raw = ast.literal_eval(ambience_raw)
            except Exception:
                ambience_raw = {}
        ambience_terms = ", ".join(k for k, v in ambience_raw.items() if v is True) if isinstance(ambience_raw, dict) else ""

        # Parse price
        from search import get_price_info
        price_tier, price_label = get_price_info(business)
        price_display = price_label or (f"tier {price_tier}" if price_tier else "unknown")

        name = business.get("name", "")
        categories = business.get("categories", "")
        stars = business.get("stars", "N/A")

        # Truncate reviews to keep prompt compact
        reviews_snippet = reviews_text[:400] if reviews_text else "No reviews available."

        system_prompt = (
            "You are a restaurant recommendation assistant. "
            "Given a user query and restaurant details, write exactly 1-2 sentences "
            "explaining why this specific restaurant matches the query. "
            "Be concrete — reference the restaurant's actual attributes, not generic praise."
        )
        user_prompt = (
            f"User query: \"{query}\"\n\n"
            f"Restaurant: {name}\n"
            f"Categories: {categories}\n"
            f"Ambience: {ambience_terms or 'not specified'}\n"
            f"Price: {price_display}\n"
            f"Rating: {stars}/5\n"
            f"Review excerpts: {reviews_snippet}\n\n"
            "In 1-2 sentences, explain why this restaurant matches the user's query."
        )

        try:
            client = LLMClient(api_key=api_key)
            response = client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            explanation = (response.get("content") or "").strip()
            if not explanation:
                return jsonify({"error": "Empty response from LLM", "explanation": None}), 500
            return jsonify({"explanation": explanation, "error": None})
        except Exception as e:
            logger.error(f"LLM explain error for {business_id}: {e}")
            return jsonify({"error": "Failed to generate explanation", "explanation": None}), 500
