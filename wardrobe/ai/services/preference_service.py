from collections import defaultdict
from wardrobe.models import OutfitRating, UserPreference

class PreferenceService:
    @staticmethod
    def _normalize_key(value):
        if not value:
            return None
        return str(value).strip().lower()

    @staticmethod
    def _item_color_key(item):
        if item.color_names:
            return PreferenceService._normalize_key(item.color_names[0])

        if item.dominant_colors:
            return str(item.dominant_colors[0])

        return None

    @staticmethod
    def build_style_preferences(user):
        ratings = OutfitRating.objects.filter(
            top_item__user=user
        )

        styles = defaultdict(list)
        for rating in ratings:
            outfit_style = PreferenceService._normalize_key(rating.style)
            styles[outfit_style].append(
                rating.user_rating
            )
            styles[f"outfit:{outfit_style}"].append(
                rating.user_rating
            )

            for item in [
                rating.top_item,
                rating.bottom_item,
                rating.shoe_item,
            ]:
                if item and item.subcategory:
                    item_style = PreferenceService._normalize_key(
                        item.subcategory
                    )
                    styles[f"item:{item_style}"].append(
                        rating.user_rating
                    )

        result = {}

        for style, values in styles.items():
            result[style] = sum(values) / len(values)

        return result

    @staticmethod
    def build_color_preferences(user):
        ratings = OutfitRating.objects.filter(
            top_item__user=user
        )

        colors = defaultdict(list)

        for rating in ratings:
            top_color = PreferenceService._item_color_key(
                rating.top_item
            )
            if top_color:
                colors[top_color].append(
                    rating.user_rating
                )

            bottom_color = PreferenceService._item_color_key(
                rating.bottom_item
            )
            if bottom_color:
                colors[bottom_color].append(
                    rating.user_rating
                )

            if rating.shoe_item:
                shoe_color = PreferenceService._item_color_key(
                    rating.shoe_item
                )
                if shoe_color:
                    colors[shoe_color].append(
                        rating.user_rating
                    )

        result = {}
        for color, values in colors.items():
            result[color] = (
                sum(values) / len(values)
            )

        return result

    @staticmethod
    def build_material_preferences(user):

        ratings = OutfitRating.objects.filter(
            top_item__user=user
        )

        materials = defaultdict(list)

        for rating in ratings:

            if rating.top_item.material:
                material = PreferenceService._normalize_key(
                    rating.top_item.material
                )
                materials[material].append(
                    rating.user_rating
                )

            if rating.bottom_item.material:
                material = PreferenceService._normalize_key(
                    rating.bottom_item.material
                )
                materials[material].append(
                    rating.user_rating
                )

            if rating.shoe_item and rating.shoe_item.material:
                material = PreferenceService._normalize_key(
                    rating.shoe_item.material
                )
                materials[material].append(
                    rating.user_rating
                )

        result = {}

        for material, values in materials.items():
            result[material] = (
                sum(values) / len(values)
            )

        return result

    @staticmethod
    def update_user_preferences(user):

        import time

        start = time.time()

        pref, _ = UserPreference.objects.get_or_create(
            user=user
        )

        pref.style_preferences = (
            PreferenceService.build_style_preferences(
                user
            )
        )

        pref.material_preferences = (
            PreferenceService.build_material_preferences(
                user
            )
        )

        pref.color_preferences = (
            PreferenceService.build_color_preferences(
                user
            )
        )

        pref.save()

        print(f"Preference update: {time.time() - start:.2f}s")

    @staticmethod
    def calculate_bonus(
        top_item,
        bottom_item,
        shoe_item,
        style,
        preferences,
    ):
        def normalize(value):
            # 1 -> -1
            # 3 -> 0
            # 5 -> +1
            return (value - 3.0) / 2.0

        bonus = 0.0

        style_prefs = preferences.style_preferences or {}
        material_prefs = preferences.material_preferences or {}
        color_prefs = preferences.color_preferences or {}

        # Style preference
        style_key = PreferenceService._normalize_key(style)
        style_score = (
            style_prefs.get(style_key)
            or style_prefs.get(f"outfit:{style_key}")
        )

        if style_score is not None:
            bonus += normalize(style_score) * 0.15

        # Item style preference (subcategory, such as jeans/hoodie/shirt)
        for item in [top_item, bottom_item, shoe_item]:

            if item and item.subcategory:

                item_style = PreferenceService._normalize_key(
                    item.subcategory
                )
                item_style_score = style_prefs.get(
                    f"item:{item_style}"
                )

                if item_style_score is not None:
                    bonus += normalize(item_style_score) * 0.05

        # Material preference
        for item in [top_item, bottom_item, shoe_item]:

            if item and item.material:

                material_score = material_prefs.get(
                    PreferenceService._normalize_key(item.material)
                )

                if material_score is not None:
                    bonus += normalize(material_score) * 0.05

        # Color preference
        for item in [top_item, bottom_item, shoe_item]:

            if item:
                color_key = PreferenceService._item_color_key(item)
                color_score = color_prefs.get(
                    color_key
                )

                if color_score is not None:
                    bonus += normalize(color_score) * 0.06

        return bonus
