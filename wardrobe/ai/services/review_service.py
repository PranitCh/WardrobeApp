from wardrobe.models import OutfitRating


class ReviewService:

    @staticmethod
    def build_outfit_key(top_id, bottom_id, shoe_id, style):
        return f"{top_id}|{bottom_id}|{shoe_id or 'none'}|{style}"

    @staticmethod
    def get_review_lookup(user, style):

        ratings = (
            OutfitRating.objects
            .filter(
                top_item__user=user,
                bottom_item__user=user,
                style=style,
            )
            .select_related(
                "top_item",
                "bottom_item",
                "shoe_item",
            )
        )

        lookup = {}

        for rating in ratings:

            key = ReviewService.build_outfit_key(
                rating.top_item_id,
                rating.bottom_item_id,
                rating.shoe_item_id,
                style,
            )

            lookup[key] = {
                "avg_rating": rating.user_rating,
                "rating_count": 1,
            }

        return lookup
