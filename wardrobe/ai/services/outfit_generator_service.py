import os
from django.conf import settings
from wardrobe.models import ClothingItem, UserPreference
from wardrobe.ai.models.cached_outfit_generator import (
    process_and_cache_single,
    get_cached_combinations,
)
from .review_service import ReviewService
from wardrobe.ai.services.preference_service import PreferenceService

class OutfitGenerationService:

    STYLE_RULES = {
            "formal": {
                "top": ["shirt", "blazer"],
                "bottom": ["trousers", "chinos", "jeans"],
                "shoe": ["formal_shoes", "loafers"],
            },
            "casual": {
                "top": ["tshirt", "shirt", "hoodie"],
                "bottom": ["jeans", "cargos", "chinos", "shorts", "trackpants"],
                "shoe": ["sneakers", "sports_shoes"],
            },
            "sporty": {
                "top": ["tshirt", "hoodie"],
                "bottom": ["trackpants", "shorts"],
                "shoe": ["sports_shoes"],
            },
        }

    @staticmethod
    def get_style_items(user, style):

        items = ClothingItem.objects.filter(user=user)
        rules = OutfitGenerationService.STYLE_RULES.get[style]

        if not rules:
            raise ValueError(f"Unknown style: {style}")

        tops_qs = items.filter(category="top", subcategory__in=rules["top"])
        bottoms_qs = items.filter(category="bottom", subcategory__in=rules["bottom"])
        shoes_qs = items.filter(category="shoe", subcategory__in=rules["shoe"])

        return tops_qs, bottoms_qs, shoes_qs

    @staticmethod
    def prepare_cache(user_id, tops, bottoms, shoes):
        cache_base = os.path.join(settings.MEDIA_ROOT, "cache", str(user_id))
        top_cache = os.path.join(cache_base, "top")
        bottom_cache = os.path.join(cache_base, "bottom")
        shoe_cache = os.path.join(cache_base, "shoe")

        os.makedirs(top_cache, exist_ok=True)
        os.makedirs(bottom_cache, exist_ok=True)
        os.makedirs(shoe_cache, exist_ok=True)

        for img in tops:
            process_and_cache_single((img, top_cache, True, "rembg"))
        for img in bottoms:
            process_and_cache_single((img, bottom_cache, True, "rembg"))
        for img in shoes:
            process_and_cache_single((img, shoe_cache, True, "rembg"))

        return top_cache, bottom_cache, shoe_cache

    @staticmethod
    def generate_outfits(
        user,
        style,
        weather_profile=None,
        threshold=0.6,
        limit = 10
    ):
        
        tops_qs, bottoms_qs, shoes_qs = (
            OutfitGenerationService.get_style_items(user, style)
        )

        if not tops_qs.exists():
            raise ValueError(
                f"No matching tops found for {style}"
            )

        if not bottoms_qs.exists():
            raise ValueError(
                f"No matching bottoms found for {style}"
            )

        tops = [i.image.path for i in tops_qs if i.image]
        bottoms = [i.image.path for i in bottoms_qs if i.image]
        shoes = [i.image.path for i in shoes_qs if i.image]

        top_cache, bottom_cache, shoe_cache = (
            OutfitGenerationService.prepare_cache(
                user.id,
                tops,
                bottoms,
                shoes
            )
        )

        review_lookup = ReviewService.get_review_lookup(user, style)

        results = get_cached_combinations(
            tops=tops,
            bottoms=bottoms,
            shoes=shoes if shoes else [None],
            top_cache=top_cache,
            bottom_cache=bottom_cache,
            shoe_cache=shoe_cache,
            outfit_type=style,
            threshold=0.6,
            review_lookup=review_lookup,
            review_weight=0.25,
            weather_profile=weather_profile,
        )

        pref = UserPreference.objects.filter(user=user).first()
        if pref:
            for result in results:

                top_item = next((item for item in tops_qs if item.image.path == result["top"]), None)
                bottom_item = next((item for item in bottoms_qs if item.image.path == result["botton"]), None)
                shoe_item = next((item for item in shoes_qs if item.image.path == result["shoe"]), None)

                result["score"] += (
                    PreferenceService.calculate_bonus(
                        tops_qs,
                        bottoms_qs,
                        shoes_qs,
                        style,
                        pref
                    )
                )

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        has_more = len(results) > limit
        results = results[:limit]
        outfit_cards = []
        for result in results:
            top_item = next((item for item in tops_qs if item.image.path == result["top"]), None)
            bottom_item = next((item for item in bottoms_qs if item.image.path == result["bottom"]), None)
            shoe_item = next((item for item in shoes_qs if item.image.path == result["shoe"]), None)

            outfit_cards.append({
                "top": top_item,
                "bottom": bottom_item,
                "shoe": shoe_item,
                "score": result["score"],
                "top_color": result.get("top_color"),
                "bottom_color": result.get("bottom_color"),
                "shoe_color": result.get("shoe_color"),
            })


        return outfit_cards, has_more