from collections import defaultdict
from wardrobe.models import OutfitRating, UserPreference

class PreferenceService:

    @staticmethod
    def build_style_preferences(user):
        ratings = OutfitRating.objects.filter(
            top_item__user=user
        )

        styles = defaultdict(list)
        for rating in ratings:
            styles[rating.style].append(
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
            if rating.top_item.dominant_colors:
                top_color = str(
                    rating.top_item.dominant_colors[0]
                )
                colors[top_color].append(
                    rating.user_rating
                )

            if rating.bottom_item.dominant_colors:
                bottom_color = str(
                    rating.bottom_item.dominant_colors[0]
                )
                colors[bottom_color].append(
                    rating.user_rating
                )

            if rating.shoe_item.dominant_colors:
                shoe_color = str(
                    rating.shoe_item.dominant_colors[0]
                )
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
                materials[rating.top_item.material].append(
                    rating.user_rating
                )

            if rating.bottom_item.material:
                materials[rating.bottom_item.material].append(
                    rating.user_rating
                )

            if rating.shoe_item and rating.shoe_item.material:
                materials[rating.shoe_item.material].append(
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
        style_score = style_prefs.get(style)

        if style_score is not None:
            bonus += normalize(style_score) * 0.15

        # Material preference
        for item in [top_item, bottom_item, shoe_item]:

            if item and item.material:

                material_score = material_prefs.get(
                    item.material
                )

                if material_score is not None:
                    bonus += normalize(material_score) * 0.05

        # Color preference
        for item in [top_item, bottom_item, shoe_item]:

            if (
                item
                and item.dominant_colors
                and len(item.dominant_colors) > 0
            ):
                dominant_color = str(
                    item.dominant_colors[0]
                )

                color_score = color_prefs.get(
                    dominant_color
                )

                if color_score is not None:
                    bonus += normalize(color_score) * 0.03

        return bonus