from django.contrib import admin
from .models import Category, Series, Book, Review, Cart, CartItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'emoji']
    search_fields = ['name']

@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ['name', 'books_in_series', 'total_books']
    search_fields = ['name']
    
    def books_in_series(self, obj):
        return obj.books_in_series
    books_in_series.short_description = 'Books in Series'

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'series', 'series_order', 'price', 'quantity', 'stock_status', 'category', 'is_featured', 'is_bestseller', 'created_at']
    list_filter = ['category', 'series', 'is_featured', 'is_bestseller', 'created_at']
    search_fields = ['title', 'author', 'series__name']
    list_editable = ['price', 'quantity', 'series', 'series_order', 'is_featured', 'is_bestseller']
    
    def stock_status(self, obj):
        return obj.stock_status
    stock_status.short_description = 'Stock Status'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['book', 'user', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['book__title', 'user__username', 'comment']

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_items', 'total_price', 'created_at']
    search_fields = ['user__username']
    
    def total_items(self, obj):
        return obj.total_items
    total_items.short_description = 'Total Items'
    
    def total_price(self, obj):
        return f"{obj.total_price} TND"
    total_price.short_description = 'Total Price'

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'book', 'quantity', 'total_price', 'added_at']
    list_filter = ['added_at']
    search_fields = ['book__title', 'cart__user__username']
    
    def total_price(self, obj):
        return f"{obj.total_price} TND"
    total_price.short_description = 'Total Price'