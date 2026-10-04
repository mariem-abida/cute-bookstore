from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Category(models.Model):
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10, default='📚')
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return f"{self.emoji} {self.name}"

class Series(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    total_books = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name
    
    @property
    def books_in_series(self):
        return self.book_set.count()

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True)
    series_order = models.PositiveIntegerField(null=True, blank=True, help_text="Order in the series (1 for first book, 2 for second, etc.)")
    is_featured = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    @property
    def in_stock(self):
        return self.quantity > 0
    
    @property
    def stock_status(self):
        if self.quantity == 0:
            return "Out of Stock ❌"
        elif self.quantity <= 5:
            return f"Low Stock ({self.quantity}) ⚠️"
        else:
            return f"In Stock ({self.quantity}) ✅"
    
    @property
    def series_info(self):
        if self.series and self.series_order:
            return f"Book {self.series_order} of {self.series.name}"
        elif self.series:
            return f"Part of {self.series.name}"
        return ""

class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review for {self.book.title} by {self.user.username}"

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart ({self.user.username})"
    
    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quantity} x {self.book.title}"
    
    @property
    def total_price(self):
        return self.quantity * self.book.price
    
    def save(self, *args, **kwargs):
        # Check if there's enough stock before adding to cart
        if self.quantity > self.book.quantity:
            raise ValueError(f"Not enough stock. Only {self.book.quantity} available.")
        super().save(*args, **kwargs)
