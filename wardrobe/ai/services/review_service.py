# wardrobe/ai/services/review_service.py

import os

from wardrobe.models import OutfitRating


class ReviewService:

    @staticmethod
    def build_outfit_key(top_path, bottom_path, shoe_path, style):
        top_key = (
            os.path.splitext(os.path.basename(top_path))[0]
            if top_path else "none"
        )

        bottom_key = (
            os.path.splitext(os.path.basename(bottom_path))[0]
            if bottom_path else "none"
        )

        shoe_key = (
            os.path.splitext(os.path.basename(shoe_path))[0]
            if shoe_path else "none"
        )

        return f"{top_key}|{bottom_key}|{shoe_key}|{style}"

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

            top_path = (
                rating.top_item.image.path
                if rating.top_item and rating.top_item.image
                else None
            )

            bottom_path = (
                rating.bottom_item.image.path
                if rating.bottom_item and rating.bottom_item.image
                else None
            )

            shoe_path = (
                rating.shoe_item.image.path
                if rating.shoe_item and rating.shoe_item.image
                else None
            )

            key = ReviewService.build_outfit_key(
                top_path,
                bottom_path,
                shoe_path,
                style,
            )

            lookup[key] = {
                "avg_rating": rating.user_rating,
                "rating_count": 1,
            }

        return lookup