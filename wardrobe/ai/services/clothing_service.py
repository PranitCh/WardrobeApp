from wardrobe.models import ClothingItem
from wardrobe.ai.services.ml_client import MLClient
from wardrobe.ai.style_options import STYLE_LABELS, STYLE_SLUGS


class ClothingService:
    USER_STYLE_SCORE_FLOOR = 1.0
    MAX_USER_STYLE_CHOICES = 3

    @staticmethod
    def get_dashboard_items(user):
        items = ClothingItem.objects.filter(user=user)

        tops = items.filter(category="top")
        bottoms = items.filter(category="bottom")
        shoes = items.filter(category="shoe")

        return tops, bottoms, shoes
    
    @staticmethod
    def delete_item(item):
        if item.image:
            item.image.delete(save=False)

        if item.preview_image:
            item.preview_image.delete(save=False)

        item.delete()

    @staticmethod
    def create_preview(item):
        return item

    @staticmethod
    def get_ranked_styles(item, limit=None):
        scores = item.style_scores or {}
        ranked = []

        for slug, score in scores.items():
            if slug not in STYLE_SLUGS:
                continue

            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                continue

            ranked.append(
                {
                    "slug": slug,
                    "label": STYLE_LABELS.get(slug, slug),
                    "score": numeric_score,
                }
            )

        ranked.sort(key=lambda style: style["score"], reverse=True)

        if limit:
            return ranked[:limit]

        return ranked

    @staticmethod
    def get_suggested_style(item):
        ranked = ClothingService.get_ranked_styles(item, limit=1)

        if not ranked:
            return None

        return ranked[0]

    @staticmethod
    def apply_user_style_choice(item, style):
        return ClothingService.apply_user_style_choices(item, [style])

    @staticmethod
    def apply_user_style_choices(item, styles):
        styles = [
            style
            for style in dict.fromkeys(styles)
            if style
        ]

        if not styles:
            raise ValueError("Select at least one style.")

        if len(styles) > ClothingService.MAX_USER_STYLE_CHOICES:
            raise ValueError("Select up to 3 styles.")

        invalid_styles = [
            style
            for style in styles
            if style not in STYLE_SLUGS
        ]

        if invalid_styles:
            raise ValueError("Unknown style selected.")

        scores = item.style_scores or {}
        numeric_scores = []

        for score in scores.values():
            try:
                numeric_scores.append(float(score))
            except (TypeError, ValueError):
                continue

        base_user_score = max(
            [ClothingService.USER_STYLE_SCORE_FLOOR, *numeric_scores]
        ) + 0.01

        item.style_scores = {**scores}

        for index, style in enumerate(styles):
            item.style_scores[style] = (
                base_user_score
                + ((len(styles) - index - 1) * 0.01)
            )

        item.save(update_fields=["style_scores"])

        return item

    @staticmethod
    def process_item(item):

        result = MLClient.analyze(item.image.path)

        color_data = result["colors"]
        material_data = result["material"]
        style_scores = result.get("style_scores") or {}

        item.dominant_colors = color_data["colors_rgb"]
        item.color_percentages = color_data["percentages"]
        item.color_names = (
            color_data.get("color_names")
            or color_data.get("colors_names")
        )

        item.material = material_data.get("material")
        item.weight = material_data.get("weight")
        item.breathability = material_data.get("breathability")
        item.histogram = (
            color_data.get("histogram")
            or material_data.get("histogram")
            or []
        )
        item.style_scores = style_scores
        item.ai_processed = True

        item.save()

        return item
