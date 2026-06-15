from rest_framework import serializers
from .models import ClothingItem, OutfitRating

class ClothingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClothingItem
        fields = '__all__'

class OutfitRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutfitRating
        fields = '__all__'