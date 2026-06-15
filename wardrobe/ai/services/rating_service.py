from django.shortcuts import get_object_or_404

from wardrobe.models import ClothingItem, OutfitRating
from wardrobe.ai.services.preference_service import PreferenceService

class RatingService:

    @staticmethod
    def save_rating(
        user,
        top_id,
        bottom_id,
        shoe_id,
        style,
        generated_score,
        user_rating,
    ):

        top_item = get_object_or_404(
            ClothingItem,
            id=top_id,
            user=user,
        )

        bottom_item = get_object_or_404(
            ClothingItem,
            id=bottom_id,
            user=user,
        )

        shoe_item = None

        if shoe_id:
            shoe_item = get_object_or_404(
                ClothingItem,
                id=shoe_id,
                user=user,
            )

        user_rating = int(user_rating)

        if user_rating < 1 or user_rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        generated_score = float(generated_score)

        rating, _ = OutfitRating.objects.update_or_create(
            top_item=top_item,
            bottom_item=bottom_item,
            shoe_item=shoe_item,
            style=style,
            defaults={
                "generated_score": generated_score,
                "user_rating": user_rating,
            },
        )

        PreferenceService.update_user_preferences(
            user
        )

        return rating
