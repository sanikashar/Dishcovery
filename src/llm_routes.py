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


def register_rag_search_route(app):
    """Register full RAG pipeline:
       Step 1: LLM rewrites query for IR.
       Step 2: Run IR retrieval on transformed query.
       Step 3: LLM synthesizes an answer from the original query + IR results.
    """
    from search import restaurant_search

    @app.route("/api/rag-search")
    def rag_search():
        original_query = request.args.get("q", "").strip()
        if not original_query:
            return jsonify({"error": "Query is required", "results": [], "transformed_query": None})

        api_key = os.getenv("SPARK_API_KEY")
        if not api_key:
            ir_result = restaurant_search(original_query)
            ir_result["transformed_query"] = None
            return jsonify(ir_result)

        client = LLMClient(api_key=api_key)

        # Query transformation
        transformed_query = original_query
        try:
            transform_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a search query optimizer for a restaurant recommendation system. "
                        "Rewrite the user's query to extract key searchable terms: cuisine type, ambience/vibe words, "
                        "dining occasion, and food preferences. Keep any city name present in the query. "
                        "Remove filler words like 'I want', 'looking for', 'find me'. "
                        "Output ONLY the improved search query as a short phrase, nothing else."
                    ),
                },
                {"role": "user", "content": original_query},
            ]
            response = client.chat(transform_messages)
            transformed = (response.get("content") or "").strip()
            if transformed:
                transformed_query = transformed
        except Exception as e:
            logger.warning(f"Query transform failed, using original: {e}")

        # IR retrieval with transformed query
        ir_result = restaurant_search(transformed_query)
        results = ir_result.get("results", [])

        # AI overview from top results
        ai_overview = None
        if results:
            # Prompt written and _fmt_result debugged with limited help of GenAI
            def _fmt_result(r, rank):
                ambience = ", ".join(r.get("ambience") or []) or "not specified"
                categories = (r.get("categories") or "")
                if isinstance(categories, list):
                    categories = ", ".join(categories)
                price = r.get("priceRange") or (
                    "$" * r["priceTier"] if r.get("priceTier") else "unknown"
                )
                score = round((r.get("matchScore") or 0) * 100)
                hours_raw = r.get("hours") or {}
                hours_str = "; ".join(
                    f"{day}: {h}" for day, h in list(hours_raw.items())[:3]
                ) if hours_raw else "not available"
                return (
                    f"{rank}. {r.get('name')} — {score}% match\n"
                    f"   Categories: {categories[:120]}\n"
                    f"   Ambience tags: {ambience}\n"
                    f"   Rating: {r.get('stars') or r.get('rating') or 'N/A'}/5  Price: {price}\n"
                    f"   Hours (sample): {hours_str}"
                )

            results_summary = "\n\n".join(
                _fmt_result(r, i + 1) for i, r in enumerate(results[:5])
            )
            query_note = (
                f"Original user query: \"{original_query}\"\n"
                f"Optimized search query used: \"{transformed_query}\""
                if transformed_query != original_query
                else f"Query: \"{original_query}\""
            )
            try:
                overview_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful restaurant recommendation assistant. "
                            "Given a user's search query and the top matching restaurants with their details, "
                            "write a 2-3 sentence overview summarizing what kinds of options were found "
                            "and why they match the query. Reference specific restaurant names, ambience tags, "
                            "cuisine types, or ratings where relevant. Be specific and concise. No bullet points."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{query_note}\n\n"
                            f"Top matching restaurants:\n\n{results_summary}\n\n"
                            "Write a 2-3 sentence overview of these results."
                        ),
                    },
                ]
                overview_response = client.chat(overview_messages)
                ai_overview = (overview_response.get("content") or "").strip() or None
            except Exception as e:
                logger.warning(f"AI overview generation failed: {e}")

        shown_transformed = transformed_query
        return jsonify({
            "error": ir_result.get("error"),
            "results": results,
            "query_latent_dimensions": ir_result.get("query_latent_dimensions"),
            "transformed_query": shown_transformed,
            "ai_overview": ai_overview,
        })


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
        transformed_query = (data.get("transformed_query") or "").strip()

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
        reviews_snippet = reviews_text[:900] if reviews_text else "No reviews available."

        system_prompt = (
            "You are a restaurant recommendation assistant. "
            "Given a user query and restaurant details, write exactly 1-2 sentences "
            "explaining why this specific restaurant matches the query. "
            "Be concrete — reference the restaurant's actual attributes, not generic praise."
        )
        query_line = f"User query: \"{query}\""
        if transformed_query and transformed_query != query:
            query_line += f"\nOptimized search query: \"{transformed_query}\""
        user_prompt = (
            f"{query_line}\n\n"
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
