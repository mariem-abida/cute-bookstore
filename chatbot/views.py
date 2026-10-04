# chatbot/views.py

import json
import re
from decimal import Decimal
from difflib import get_close_matches

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from books.models import Book

from .llm import generate_answer


def _normalize_text(text: str) -> str:
    """
    Remplace les guillemets typographiques et autres caractères communs
    qui peuvent poser problème dans la détection de titres.
    """
    if not text:
        return ""
    return (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


# --- VOCABULAIRE DE RÉFÉRENCE POUR LE FUZZY MATCHING ---

INTENT_KEYWORDS = [
    "recommend",
    "suggest",
    "bestseller",
    "popular",
    "stock",
    "available",
    "price",
    "cost",
    "cheap",
    "expensive",
]

GENRE_KEYWORDS = [
    "fantasy",
    "romance",
    "mystery",
    "history",
    "historical",
    "horror",
    "children",
    "adventure",
    "self-help",
    "selfhelp",
    "science",
    "poetry",
    "non-fiction",
    "fiction",
    "classic",
]

GENRE_SYNONYMS = {
    "romantic": "romance",
    "scary": "horror",
    "kid": "children",
    "kids": "children",
    "child": "children",
    "children": "children",
    "thriller": "mystery",
}


def _normalize_intents_and_genres(message: str):
    """
    Fait du fuzzy matching sur chaque mot du message pour retrouver :
    - les mots d'intention ('recommend', 'bestseller', 'price', etc.)
    - les genres ('fantasy', 'romance', etc.)
    Même si l'utilisateur écrit mal ('recomend', 'fantazy', etc.)
    """
    msg = message.lower()
    tokens = re.findall(r"\w+", msg)

    intent_terms = set()
    genre_terms = set()

    for tok in tokens:
        # synonymes genres simples
        if tok in GENRE_SYNONYMS:
            genre_terms.add(GENRE_SYNONYMS[tok])

        # ✅ EVITER que 'story' / 'stories' deviennent 'history'
        if tok in ["story", "stories"]:
            # on ne fait PAS de fuzzy matching sur les genres pour ces mots
            continue

        # fuzzy matching sur les intents
        match_intent = get_close_matches(tok, INTENT_KEYWORDS, n=1, cutoff=0.8)
        if match_intent:
            intent_terms.add(match_intent[0])

        # fuzzy matching sur les genres
        match_genre = get_close_matches(tok, GENRE_KEYWORDS, n=1, cutoff=0.8)
        if match_genre:
            genre_terms.add(match_genre[0])

    return intent_terms, genre_terms


def _extract_author_from_message(message: str) -> str | None:
    """
    Extraction d'auteur depuis des patterns standard.
    """
    msg = message.lower()

    if "books by" in msg:
        start = msg.find("books by") + len("books by")
        author = message[start:].strip(" ?!.,\"'")
        return author or None

    # pattern: 'by Victor Hugo' (à la fin)
    if " by " in msg:
        idx = msg.rfind(" by ")
        possible_author = message[idx + 4 :].strip(" ?!.,\"'")
        if possible_author and len(possible_author.split()) <= 4:
            return possible_author

    return None


def _extract_title_from_price_question(message: str) -> str | None:
    """
    Extraction de titre dans une question sur le prix.
    """
    msg = message.lower()
    text = message

    # 1) Titre entre quotes
    m = re.search(r"[\"']([^\"']+)[\"']", text)
    if m:
        title = m.group(1).strip()
        if title:
            return title

    # 2) Pattern: 'price of X'
    key = "price of"
    if key in msg:
        start = msg.find(key) + len(key)
        title = text[start:].strip(" ?!.,\"'")
        return title or None

    # 3) Pattern: 'cost of X'
    key = "cost of"
    if key in msg:
        start = msg.find(key) + len(key)
        title = text[start:].strip(" ?!.,\"'")
        return title or None

    # 4) Pattern: 'how much does X cost'
    if "how much does" in msg and "cost" in msg:
        start = msg.find("how much does") + len("how much does")
        end = msg.rfind("cost")
        if end > start:
            title = text[start:end].strip(" ?!.,\"'")
            return title or None

    return None


def _extract_title_from_availability_question(message: str) -> str | None:
    """
    Extraction de titre pour les questions de disponibilité.
    """
    msg = message.lower()
    text = message

    # Titre entre quotes
    m = re.search(r"[\"']([^\"']+)[\"']", text)
    if m:
        title = m.group(1).strip()
        if title:
            return title

    # pattern: 'is X in stock'
    if "is" in msg and "in stock" in msg:
        start = msg.find("is") + len("is")
        end = msg.find("in stock")
        if end > start:
            title = text[start:end].strip(" ?!.,\"'")
            return title or None

    # pattern: 'do you have X'
    if "do you have" in msg:
        start = msg.find("do you have") + len("do you have")
        title = text[start:].strip(" ?!.,\"'")
        return title or None

    return None


def _extract_price_limit(message: str, direction: str) -> Decimal | None:
    """
    Extrait un montant numérique pour un filtre de prix.
    direction = 'under' ou 'over'.
    """
    msg = message.lower()

    if direction == "under":
        if "under" in msg or "less than" in msg or "cheaper than" in msg:
            match = re.search(r"(\d+(\.\d+)?)", msg)
            if match:
                return Decimal(match.group(1))

    if direction == "over":
        if (
            "over" in msg
            or "more than" in msg
            or "greater than" in msg
            or "above" in msg
        ):
            match = re.search(r"(\d+(\.\d+)?)", msg)
            if match:
                return Decimal(match.group(1))

    return None


@csrf_exempt
def chatbot_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Use POST method."}, status=405)

    # Parse JSON body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    # Normalisation
    message = data.get("message", "").strip()
    message = _normalize_text(message)
    if not message:
        # Accueil personnalisé
        return JsonResponse(
            {
                "reply": (
                    "Welcome! How may I assist you in exploring our book collection today?"
                )
            }
        )

    msg_lower = message.lower()

    # --- greetings / small talk simples ---
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if any(msg_lower.startswith(g) for g in greetings) or msg_lower in greetings:
        return JsonResponse(
            {
                "reply": (
                    "Hi 👋 I’m your Pastel Pages assistant.\n"
                    "You can ask me about authors, book titles, best sellers, prices "
                    "or which books are in stock. For example:\n"
                    "- Show me books by George Orwell\n"
                    "- What are your best sellers?\n"
                    "- Recommend me a fun book to read\n"
                    "- How much does The Hobbit cost?"
                )
            }
        )

    # Détection fuzzy intents + genres
    intent_terms, genre_terms = _normalize_intents_and_genres(message)

    # --- Recommendation intent, très flexible ---
    recommend_triggers = [
        "recommend",
        "suggest",
        "what should i read",
        "something to read",
        "anything to read",
        "interesting to read",
        "any suggestion",
        "any suggestions",
        "recommendation",
        "fun book",
        "books more fun",
        "good book",
        "nice book",
        "i'm bored",
        "i am bored",
        "i don't know what to read",
        "i dont know what to read",
        "don't know what to read",
        "dont know what to read",
        "what should i read tonight",
        "what should i read today",
        "what should i read now",
        "what can i read",
        "i want a new story",
        "new story",
        "new book to read",
        "give me something to read",
        "give me a book",
        "give me a story to read",
        "a story please",
        "story please",
        "something good",
        "something nice",
        "good read",
        "nice story",
    ]

    is_recommend = (
        "recommend" in intent_terms
        or "suggest" in intent_terms
        or any(phrase in msg_lower for phrase in recommend_triggers)
    )

    # Heuristiques supplémentaires pour capter des phrases floues
    if not is_recommend:
        # ex: "I don't know what to read, help me."
        if "read" in msg_lower and "help" in msg_lower:
            is_recommend = True
        # ex: "I'm bored, give me something."
        elif "bored" in msg_lower and (
            "book" in msg_lower or "read" in msg_lower or "something" in msg_lower
        ):
            is_recommend = True
        # ex: "I want a story", "i want new stori", "giv me story"
        elif ("story" in msg_lower or "stori" in msg_lower) and (
            "want" in msg_lower or "give" in msg_lower or "giv" in msg_lower or "please" in msg_lower
        ):
            is_recommend = True
        # ex: "Something good?", "something nice?"
        elif "something good" in msg_lower or "something nice" in msg_lower:
            is_recommend = True

    is_best = (
        "bestseller" in intent_terms
        or "popular" in intent_terms
        or "best seller" in msg_lower
        or "top selling" in msg_lower
        or "popular" in msg_lower
        or "most popular" in msg_lower
        or "what do people buy" in msg_lower
        or "people buy the most" in msg_lower
        or "most people buy" in msg_lower
    )

    is_stock_query = (
        "stock" in intent_terms
        or "available" in intent_terms
        or "in stock" in msg_lower
        or "available" in msg_lower
        or "do you have" in msg_lower
    )

    # ✅ Cas spéciaux : en fait, c'est une demande de recommandation
       # 🔥 Nouveau : détecter les "Do you have ... ?" flous
    vague_do_you_have = [
        "do you have a book",
        "do you have something",
        "do you have anything",
        "do you have any book",
        "do you have a story",
        "do you have a good",
        "do you have a nice",
        "do you have some",
        "do you have another",
        "do you have a light",
        "do you have a funny",
        "do you have a romantic",
        "do you have a scary",
        "do you have a book with",
        "do you have a story with",
        "do you have a book for",
        "do you have the great gatsby in stock or any similar story",
    ]

    if is_stock_query and any(p in msg_lower for p in vague_do_you_have):
        is_stock_query = False
        is_recommend = True


    is_price_query = (
        "price" in intent_terms
        or "cost" in intent_terms
        or "price" in msg_lower
        or "how much" in msg_lower
        or "cost" in msg_lower
    )

    # --- 1️⃣ Filtrage par fourchette de prix ---
    price_under = None
    price_over = None

    talks_about_price = any(
        w
        in msg_lower
        for w in [
            "price",
            "cost",
            "tnd",
            "cheap",
            "expensive",
            "not expensive",
            "affordable",
            "less than",
            "under",
            "more than",
            "over",
        ]
    )

    # Éviter de confondre avec des questions sur nb copies
    if talks_about_price and "copies" not in msg_lower:
        price_under = _extract_price_limit(message, direction="under")
        price_over = _extract_price_limit(message, direction="over")

    # Si 'cheap' mais pas de nombre, on prend une limite par défaut
    if price_under is None and "copies" not in msg_lower:
        cheap_words = ["cheap", "not expensive", "affordable", "low price"]
        if any(w in msg_lower for w in cheap_words):
            price_under = Decimal("20")

    if price_under is not None:
        books = Book.objects.filter(price__lte=price_under).order_by("price")[:10]
        if not books:
            reply = f"I couldn't find any books under {price_under} TND."
        else:
            lines = [f"- {b.title} by {b.author} ({b.price} TND)" for b in books]
            reply = f"Here are some books under {price_under} TND:\n" + "\n".join(lines)
        return JsonResponse({"reply": reply})

    if price_over is not None:
        books = Book.objects.filter(price__gte=price_over).order_by("-price")[:10]
        if not books:
            reply = f"I couldn't find any books over {price_over} TND."
        else:
            lines = [f"- {b.title} by {b.author} ({b.price} TND)" for b in books]
            reply = f"Here are some books over {price_over} TND:\n" + "\n".join(lines)
        return JsonResponse({"reply": reply})

    # --- 2️⃣ Prix d'un livre précis ---
    if is_price_query:
        possible_title = _extract_title_from_price_question(message)
        if possible_title:
            books = Book.objects.filter(title__icontains=possible_title)
            if not books:
                reply = (
                    f"I couldn't find any book with a title similar to '{possible_title}'."
                )
            elif books.count() == 1:
                b = books.first()
                reply = (
                    f"'{b.title}' by {b.author} costs {b.price} TND. "
                    f"We currently have {b.quantity} in stock."
                )
            else:
                lines = [
                    f"- '{b.title}' by {b.author}: {b.price} TND" for b in books
                ]
                reply = "I found several books matching that title:\n" + "\n".join(lines)
            return JsonResponse({"reply": reply})
        # sinon on passe à la suite

    # --- 3️⃣ Best sellers ---
    if is_best:
        books = Book.objects.filter(is_bestseller=True)[:5]
        if not books:
            reply = "I couldn't find any best sellers in the store yet."
        else:
            lines = [f"- {b.title} by {b.author} ({b.price} TND)" for b in books]
            reply = "Here are some best sellers in the bookstore:\n" + "\n".join(lines)
        return JsonResponse({"reply": reply})

    # --- 4️⃣ Livres par auteur ---
    author_name = _extract_author_from_message(message)
    if author_name:
        books = Book.objects.filter(author__icontains=author_name)
        if not books:
            reply = f"I couldn't find any books by '{author_name}' in our catalog."
        else:
            lines = [
                f"- {b.title} ({b.price} TND, {'in stock' if b.quantity > 0 else 'out of stock'})"
                for b in books
            ]
            reply = f"Here are books by {author_name}:\n" + "\n".join(lines)
        return JsonResponse({"reply": reply})

    # --- 5️⃣ Disponibilité / stock ---
    if is_stock_query:
        possible_title = _extract_title_from_availability_question(message)
        if possible_title:
            books = Book.objects.filter(title__icontains=possible_title)
            if not books:
                reply = (
                    f"I couldn't find any book with a title similar to '{possible_title}'."
                )
            else:
                lines = []
                for b in books:
                    status = "in stock" if b.quantity > 0 else "out of stock"
                    lines.append(
                        f"- '{b.title}' by {b.author}: {status} (qty: {b.quantity}, {b.price} TND)"
                    )
                reply = "Here is what I found:\n" + "\n".join(lines)
            return JsonResponse({"reply": reply})

        # sinon liste générale des livres en stock
        books = Book.objects.filter(quantity__gt=0).order_by("title")[:10]
        if not books:
            reply = "At the moment, no books are in stock."
        else:
            lines = [f"- {b.title} by {b.author} ({b.price} TND)" for b in books]
            reply = (
                "Here are some books that are currently in stock:\n" + "\n".join(lines)
            )
        return JsonResponse({"reply": reply})

    # --- 6️⃣ Recommandation (avec GENRE + IA) ---
    if is_recommend:
        # récupération du genre détecté
        genre = next(iter(genre_terms), None)

        if genre:
            books_qs = Book.objects.filter(
                Q(category__name__icontains=genre) | Q(description__icontains=genre)
            )
        else:
            # fallback vers best sellers puis tout
            books_qs = Book.objects.filter(is_bestseller=True)
            if not books_qs.exists():
                books_qs = Book.objects.all()

        books_qs = books_qs.order_by("?")[:5]

        # conversion pour l'IA
        books_list = [
            {
                "title": b.title,
                "author": b.author,
                "price": float(b.price),
                "quantity": b.quantity,
                "category": b.category.name,
                "is_bestseller": b.is_bestseller,
            }
            for b in books_qs
        ]

        if not books_list:
            reply = "I couldn't find any books to recommend right now."
        else:
            # appel à l'IA pour rédiger une réponse plus naturelle
            reply = generate_answer(
                user_message=message,
                books=books_list,
                intent_type="recommendation",
            )

        return JsonResponse({"reply": reply})

    # --- 7️⃣ Livres par catégorie / genre ---
    if genre_terms:
        genre = next(iter(genre_terms))
        books = Book.objects.filter(
            Q(category__name__icontains=genre) | Q(description__icontains=genre)
        )[:10]
        if not books:
            reply = f"I couldn't find any books in the '{genre}' category."
        else:
            lines = [f"- {b.title} by {b.author} ({b.price} TND)" for b in books]
            reply = f"Here are some {genre} books:\n" + "\n".join(lines)
        return JsonResponse({"reply": reply})

    # --- 8️⃣ Questions générales sur l'inventaire ---
    if (
        "all books" in msg_lower
        or "what books do you have" in msg_lower
        or "show me your books" in msg_lower
        or "show me all books" in msg_lower
    ):
        books = Book.objects.all().order_by("title")[:20]
        if not books:
            reply = "The bookstore is currently empty."
        else:
            lines = [f"- {b.title} by {b.author} ({b.price} TND)" for b in books]
            reply = "Here are some books in our store:\n" + "\n".join(lines)
        return JsonResponse({"reply": reply})

    # --- 9️⃣ FALLBACK, envoi à l'IA pour gérer le reste
    # On fournit un échantillon du catalogue pour cohérence
    sample_books = Book.objects.all()[:10]
    books_payload = [
        {
            "title": b.title,
            "author": b.author,
            "price": float(b.price),
            "quantity": b.quantity,
            "category": b.category.name,
            "is_bestseller": b.is_bestseller,
        }
        for b in sample_books
    ]

    reply = generate_answer(
        user_message=message,
        books=books_payload,
        intent_type="fallback",
    )
    return JsonResponse({"reply": reply})
