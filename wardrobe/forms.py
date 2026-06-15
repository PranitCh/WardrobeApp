from django import forms
from .models import ClothingItem

class ClothingForm(forms.ModelForm):
    class Meta:
        model = ClothingItem
        fields = ['category', 'image']