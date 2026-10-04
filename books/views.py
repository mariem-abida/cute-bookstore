from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import logout
from .models import Book, Category, Review, Cart, CartItem, Series
from .forms import ReviewForm, BookSearchForm

def home(request):
    bestsellers = Book.objects.filter(is_bestseller=True)[:3]
    categories = Category.objects.all()
    
    context = {
        'bestsellers': bestsellers,
        'categories': categories,
    }
    return render(request, 'books/home.html', context)

def book_list(request):
    books = Book.objects.all()
    query = request.GET.get('query', '')
    sort_by = request.GET.get('sort_by', 'title_asc')  # Default sort by title A-Z
    
    if query:
        books = books.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Apply sorting
    if sort_by == 'title_asc':
        books = books.order_by('title')
    elif sort_by == 'title_desc':
        books = books.order_by('-title')
    elif sort_by == 'price_low':
        books = books.order_by('price')
    elif sort_by == 'price_high':
        books = books.order_by('-price')
    elif sort_by == 'author_asc':
        books = books.order_by('author')
    elif sort_by == 'author_desc':
        books = books.order_by('-author')
    elif sort_by == 'newest':
        books = books.order_by('-created_at')
    elif sort_by == 'oldest':
        books = books.order_by('created_at')
    else:
        books = books.order_by('title')  # Default sorting
    
    form = BookSearchForm(initial={'query': query})
    
    context = {
        'books': books,
        'form': form,
        'query': query,
        'sort_by': sort_by,
    }
    return render(request, 'books/book_list.html', context)

def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    reviews = book.reviews.all().order_by('-created_at')
    
    if request.method == 'POST' and request.user.is_authenticated:
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.book = book
            review.user = request.user
            review.save()
            messages.success(request, 'Your review has been added! 🌟')
            return redirect('book_detail', book_id=book.id)
    else:
        form = ReviewForm()
    
    context = {
        'book': book,
        'reviews': reviews,
        'form': form,
    }
    return render(request, 'books/book_detail.html', context)

def category_books(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    books = Book.objects.filter(category=category)
    
    context = {
        'category': category,
        'books': books,
    }
    return render(request, 'books/category_books.html', context)

def author_books(request, author_name):
    books = Book.objects.filter(author=author_name)
    
    context = {
        'author_name': author_name,
        'books': books,
    }
    return render(request, 'books/author_books.html', context)

def series_books(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    books = series.book_set.all().order_by('series_order')
    
    context = {
        'series': series,
        'books': books,
    }
    return render(request, 'books/series_books.html', context)

@login_required
def custom_logout(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out! 🌈')
    return redirect('home')

@login_required
def add_to_cart(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart, 
        book=book
    )
    
    if not item_created:
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, f'Added another copy of "{book.title}" to your cart. 🎀')
    else:
        messages.success(request, f'Added "{book.title}" to your cart. 🌈')
    
    return redirect('book_detail', book_id=book_id)

@login_required
def cart_view(request):
    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = cart.items.all().select_related('book')
    except Cart.DoesNotExist:
        cart = None
        cart_items = []
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
    }
    return render(request, 'books/cart.html', context)

@login_required
def update_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Cart updated successfully. ✨')
        else:
            cart_item.delete()
            messages.success(request, 'Item removed from cart. 🎀')
    
    return redirect('cart_view')

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    book_title = cart_item.book.title
    cart_item.delete()
    messages.success(request, f'"{book_title}" removed from cart. 🌈')
    return redirect('cart_view')

@login_required
def clear_cart(request):
    try:
        cart = Cart.objects.get(user=request.user)
        cart.items.all().delete()
        messages.success(request, 'Your cart has been cleared successfully! 🎀')
    except Cart.DoesNotExist:
        pass
    
    return redirect('cart_view')