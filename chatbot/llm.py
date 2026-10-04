
from typing import List, Dict, Literal
import random

IntentType = Literal["recommendation", "fallback"]


def _format_book_line(book: Dict) -> str:
    """Format one book nicely for display."""
    title = book.get("title", "Unknown title")
    author = book.get("author", "Unknown author")
    price = book.get("price")

    if price is not None:
        return f"- {title} by {author} ({price} TND)"
    return f"- {title} by {author}"


def generate_answer(user_message: str, books: List[Dict], intent_type: IntentType) -> str:
    """
    Local 'AI' engine: NO external calls, NO API.
    - intent_type = 'recommendation' -> suggest books from the list
    - intent_type = 'fallback'       -> answer when we don't clearly understand
    """
    msg = (user_message or "").lower().strip()

    # -----------------------------
    # 1) RECOMMENDATION INTENT
    # -----------------------------
    if intent_type == "recommendation":
        if not books:
            return "I couldn't find any books to recommend right now."

        # detect rough genre preference from user message
        preferred = None
        if "romance" in msg or "romantic" in msg or "love story" in msg:
            preferred = "romance"
        elif "fantasy" in msg or "magic" in msg or "dragon" in msg:
            preferred = "fantasy"
        elif "mystery" in msg or "thriller" in msg or "crime" in msg:
            preferred = "mystery"
        elif "history" in msg or "historical" in msg:
            preferred = "history"

        # try to filter by that preference
        filtered = books
        if preferred:
            filtered_candidates = []
            for b in books:
                category = str(b.get("category", "")).lower()
                title = str(b.get("title", "")).lower()
                if preferred in category or preferred in title:
                    filtered_candidates.append(b)

            if filtered_candidates:
                filtered = filtered_candidates

        # pick up to 3 random books
        random.shuffle(filtered)
        top = filtered[:3]

        if preferred == "romance":
            intro = "Here are some romance books you might enjoy:\n"
        elif preferred == "fantasy":
            intro = "Here are some fantasy books you might enjoy:\n"
        elif preferred == "mystery":
            intro = "Here are some mystery books you might enjoy:\n"
        elif preferred == "history":
            intro = "Here are some historical books you might enjoy:\n"
        else:
            intro = "Here are some books I recommend for you:\n"

        lines = [_format_book_line(b) for b in top]
        return intro + "\n".join(lines)

    # -----------------------------
    # 2) FALLBACK INTENT
    # -----------------------------
    # 2.1 Questions clairement hors domaine (pizza, président, météo…)
    out_of_scope_keywords = [
        "president",
        "prime minister",
        "weather",
        "temperature",
        "pizza",
        "deliver",
        "delivery",
        "2 + 2",
        "2+2",
        "math",
        "calculate",
        "capital of",
    ]
    if any(k in msg for k in out_of_scope_keywords):
        return (
            "I'm the Pastel Pages assistant. I can help you with our books, authors, prices, "
            "best sellers and stock availability, but I can't answer general knowledge questions."
        )

    # 2.2 Messages probablement liés aux livres -> rediriger vers une recommandation
    in_scope_for_reco = [
        "book",
        "books",
        "read",
        "story",
        "stories",
        "novel",
        "romantic",
        "romance",
        "fantasy",
        "mystery",
        "history",
        "recommend",
        "suggest",
    ]
    if any(k in msg for k in in_scope_for_reco) and books:
        # On réutilise la logique de recommandation pour aider l'utilisateur
        return generate_answer(user_message, books, "recommendation")

    # 2.3 Sinon : la question parle peut-être de livres, mais on ne comprend pas bien
    examples = [
        "Show me books by George Orwell",
        "What are your best sellers?",
        "Are romance books under 30 TND available?",
        "Recommend me a fantasy book",
        "How much does The Great Gatsby cost?",
        "Show me books under 20 TND",
    ]

    bullet_examples = "\n- " + "\n- ".join(examples)

    return (
        "I'm not sure I understood your question. I can help you with our books, authors, prices, "
        "best sellers and stock availability. For example:"
        f"{bullet_examples}"
    )
