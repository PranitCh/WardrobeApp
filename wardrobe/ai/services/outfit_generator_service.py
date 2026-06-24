from wardrobe.models import ClothingItem, UserPreference
from .review_service import ReviewService
from wardrobe.ai.services.ml_client import MLClient
from wardrobe.ai.services.preference_service import PreferenceService
from wardrobe.ai.style_options import STYLE_LABELS, STYLE_OPTIONS

class OutfitGenerationService:
    STYLE_OPTIONS = STYLE_OPTIONS
    STYLE_LABELS = STYLE_LABELS
    STYLE_TOP_N = 4

    STYLE_RULES = {
            "formal": {
                "top": ["shirt", "blazer"],
                "bottom": ["trousers", "chinos", "jeans"],
                "shoe": ["formal_shoes", "loafers"],
            },
            "business_casual": {
                "top": ["shirt", "blazer", "tshirt"],
                "bottom": ["trousers", "chinos", "jeans"],
                "shoe": ["formal_shoes", "loafers", "sneakers"],
            },
            "smart_casual": {
                "top": ["shirt", "blazer", "tshirt"],
                "bottom": ["chinos", "jeans", "trousers"],
                "shoe": ["loafers", "sneakers", "formal_shoes"],
            },
            "casual": {
                "top": ["tshirt", "shirt", "hoodie"],
                "bottom": ["jeans", "cargos", "chinos", "shorts", "trackpants"],
                "shoe": ["sneakers", "sports_shoes", "slides"],
            },
            "streetwear": {
                "top": ["tshirt", "hoodie", "shirt"],
                "bottom": ["jeans", "cargos", "trackpants"],
                "shoe": ["sneakers", "sports_shoes"],
            },
            "sporty_activewear": {
                "top": ["tshirt", "hoodie"],
                "bottom": ["trackpants", "shorts"],
                "shoe": ["sports_shoes", "sneakers"],
            },
            "loungewear": {
                "top": ["tshirt", "hoodie"],
                "bottom": ["trackpants", "shorts"],
                "shoe": ["slides", "slippers", "sneakers"],
            },
            "party_night_out": {
                "top": ["shirt", "tshirt", "blazer"],
                "bottom": ["jeans", "trousers", "chinos"],
                "shoe": ["loafers", "sneakers", "formal_shoes"],
            },
            "ethnic_traditional": {
                "top": ["shirt", "tshirt", "blazer"],
                "bottom": ["trousers", "chinos"],
                "shoe": ["loafers", "formal_shoes", "slippers"],
            },
            "outdoor_adventure": {
                "top": ["tshirt", "hoodie", "shirt"],
                "bottom": ["cargos", "shorts", "trackpants", "jeans"],
                "shoe": ["sports_shoes", "sneakers"],
            },
        }

    @staticmethod
    def has_required_cached_features(item):
        colors = item.dominant_colors
        percentages = item.color_percentages

        if not colors or not percentages:
            return False

        first_color = colors[0]
        return (
            isinstance(first_color, (list, tuple))
            and len(first_color) == 3
        )

    @staticmethod
    def get_style_label(style):
        return OutfitGenerationService.STYLE_LABELS.get(style, style)

    @staticmethod
    def get_top_style_slugs(item, top_n=None):
        top_n = top_n or OutfitGenerationService.STYLE_TOP_N
        scores = item.style_scores or {}

        if not scores:
            return []

        ranked = sorted(
            scores.items(),
            key=lambda entry: entry[1],
            reverse=True,
        )

        return [
            slug
            for slug, _score in ranked[:top_n]
        ]

    @staticmethod
    def matches_style_scores(item, style):
        top_styles = OutfitGenerationService.get_top_style_slugs(item)

        if not top_styles:
            return True

        return style in top_styles

    @staticmethod
    def apply_style_score_filter(items, style):
        items = list(items)
        matched = [
            item for item in items
            if OutfitGenerationService.matches_style_scores(item, style)
        ]

        return matched or items

    @staticmethod
    def get_style_items(user, style):

        items = ClothingItem.objects.filter(user=user)

        rules = OutfitGenerationService.STYLE_RULES.get(style)

        if not rules:
            raise ValueError(f"Unknown style: {style}")

        tops_qs = items.filter(
            category="top",
            subcategory__in=rules["top"]
        )

        bottoms_qs = items.filter(
            category="bottom",
            subcategory__in=rules["bottom"]
        )

        shoes_qs = items.filter(
            category="shoe",
            subcategory__in=rules["shoe"]
        )

        tops = OutfitGenerationService.apply_style_score_filter(
            tops_qs,
            style,
        )
        bottoms = OutfitGenerationService.apply_style_score_filter(
            bottoms_qs,
            style,
        )
        shoes = OutfitGenerationService.apply_style_score_filter(
            shoes_qs,
            style,
        )

        return tops, bottoms, shoes

    @staticmethod
    def serialize_item(item):
        return {
            "id": item.id,
            "colors_rgb": item.dominant_colors,
            "percentages": item.color_percentages,
            "color_names": item.color_names,
            "material": item.material,
            "weight": item.weight,
            "breathability": item.breathability,
            "histogram": item.histogram or [],
            "style_scores": item.style_scores or {},
        }

    @staticmethod
    def generate_outfits(
        user,
        style,
        weather_profile=None,
        threshold=0.6,
        limit=10,
    ):

        tops_for_style, bottoms_for_style, shoes_for_style = (
            OutfitGenerationService.get_style_items(user, style)
        )

        if not tops_for_style:
            raise ValueError(f"No matching tops found for {style}")

        if not bottoms_for_style:
            raise ValueError(f"No matching bottoms found for {style}")

        tops = [
            item for item in tops_for_style
            if OutfitGenerationService.has_required_cached_features(item)
        ]
        bottoms = [
            item for item in bottoms_for_style
            if OutfitGenerationService.has_required_cached_features(item)
        ]
        shoes = [
            item for item in shoes_for_style
            if OutfitGenerationService.has_required_cached_features(item)
        ]

        if not tops:
            raise ValueError(
                f"No AI-processed tops found for {style}. "
                "Please re-upload or reprocess your matching tops."
            )

        if not bottoms:
            raise ValueError(
                f"No AI-processed bottoms found for {style}. "
                "Please re-upload or reprocess your matching bottoms."
            )

        review_lookup = ReviewService.get_review_lookup(
            user,
            style,
        )

        results = MLClient.score_outfits(
            {
                "tops": [
                    OutfitGenerationService.serialize_item(item)
                    for item in tops
                ],
                "bottoms": [
                    OutfitGenerationService.serialize_item(item)
                    for item in bottoms
                ],
                "shoes": [
                    OutfitGenerationService.serialize_item(item)
                    for item in shoes
                ],
                "outfit_type": style,
                "threshold": threshold,
                "review_lookup": review_lookup,
                "review_weight": 0.25,
                "weather_profile": weather_profile,
            }
        )

        pref = UserPreference.objects.filter(
            user=user
        ).first()
        items_by_id = {
            item.id: item
            for item in [*tops, *bottoms, *shoes]
        }

        for result in results:

            top_item = items_by_id.get(result["top_id"])
            bottom_item = items_by_id.get(result["bottom_id"])
            shoe_item = items_by_id.get(result["shoe_id"])

            if pref:
                preference_bonus = PreferenceService.calculate_bonus(
                    top_item,
                    bottom_item,
                    shoe_item,
                    style,
                    pref,
                )
                preference_bonus = max(
                    -0.25,
                    min(preference_bonus, 0.25),
                )
                result["preference_bonus"] = preference_bonus
                result["score"] = result["score"] + preference_bonus

            result["score"] = max(0.0, min(result["score"], 0.99))

        results.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        has_more = len(results) > limit
        results = results[:limit]

        outfit_cards = []

        for result in results:
            top_item = items_by_id.get(result["top_id"])
            bottom_item = items_by_id.get(result["bottom_id"])
            shoe_item = items_by_id.get(result["shoe_id"])

            if not top_item or not bottom_item:
                continue

            outfit_cards.append({
                "top": top_item,
                "bottom": bottom_item,
                "shoe": shoe_item,
                "score": round(result["score"], 3),
                "top_color": result.get("top_color"),
                "bottom_color": result.get("bottom_color"),
                "shoe_color": result.get("shoe_color"),
                "avg_rating": result.get("avg_rating"),
                "user_rating": result.get("avg_rating"),
                "preference_bonus": result.get("preference_bonus", 0.0),
            })

        return outfit_cards, has_more
