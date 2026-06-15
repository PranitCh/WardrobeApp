from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class ClothingItem(models.Model):
    CATEGORY_CHOICES = [
        ('top', 'Top'),
        ('bottom', 'Bottom'),
        ('shoe', 'Shoe'),
    ]

    SUBCATEGORY_CHOICES = [
        ("shirt", "Shirt"),
        ("tshirt", "T-Shirt"),
        ("blazer", "Blazer"),
        ("hoodie", "Hoodie"),

        ("trousers", "Trousers"),
        ("jeans", "Jeans"),
        ("trackpants", "Trackpants"),
        ("shorts", "Shorts"),
        ("cargos", "Cargos"),
        ("chinos", "Chinos"),

        ("formal_shoes", "Formal Shoes"),
        ("loafers", "Loafers"),
        ("sneakers", "Sneakers"),
        ("slides", "Slides"),
        ("sports_shoes", "Sports Shoes"),
        ("slippers", "Slippers"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    image = models.ImageField(upload_to='clothes/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    subcategory = models.CharField(max_length=30, choices=SUBCATEGORY_CHOICES, default="tshirt")
    preview_image = models.ImageField(upload_to="previews/", null=True, blank=True)
    material = models.CharField(max_length=50, blank=True, null=True)
    breathability = models.CharField(max_length=20, blank=True, null=True)
    weight = models.CharField(max_length=20, blank=True, null=True)
    dominant_colors = models.JSONField(null=True, blank=True)
    color_percentages = models.JSONField(null=True, blank=True)
    histogram = models.JSONField(null=True, blank=True)

    ai_processed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.subcategory}"
    
class OutfitRating(models.Model):
    top_item = models.ForeignKey(ClothingItem, on_delete=models.CASCADE, related_name="rated_top")
    bottom_item = models.ForeignKey(ClothingItem, on_delete=models.CASCADE, related_name="rated_bottom")
    shoe_item = models.ForeignKey(ClothingItem, on_delete=models.CASCADE, related_name="rated_shoe", null=True, blank=True)
    style = models.CharField(max_length=20)
    generated_score = models.FloatField()
    user_rating = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("top_item", "bottom_item", "shoe_item", "style")

class UserPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    color_preferences = models.JSONField(default=dict, blank=True)
    material_preferences = models.JSONField(default=dict, blank=True)
    style_preferences = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
