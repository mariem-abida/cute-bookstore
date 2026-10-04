from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('books/', views.book_list, name='book_list'),
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('category/<int:category_id>/', views.category_books, name='category_books'),
    path('author/<str:author_name>/', views.author_books, name='author_books'),
    path('series/<int:series_id>/', views.series_books, name='series_books'),
    
    # Cart URLs
    path('cart/add/<int:book_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # Custom logout URL
    path('logout/', views.custom_logout, name='logout'),
]