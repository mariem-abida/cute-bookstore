from django import forms
from .models import Review, Book

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'class': 'cute-textarea'}),
            'rating': forms.RadioSelect(choices=[(i, '⭐' * i) for i in range(1, 6)])
        }

class BookSearchForm(forms.Form):
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '🔍 Search for books...',
            'class': 'cute-search'
        })
    )