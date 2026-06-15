from ..models.outfit_matcher2 import OutfitMatcher

class OutfitService:

    matcher = OutfitMatcher(use_mask=True, mask_method="rembg")

    @staticmethod
    def score_pair(top_feat, bottom_feat):
        return OutfitService.matcher.calculate_two_item_compatibility(
            top_feat, bottom_feat
        )

    @staticmethod
    def score_shoes(outfit_colors, shoe_feat, style="casual"):
        return OutfitService.matcher.calculate_shoe_compatibility(
            outfit_colors,
            shoe_feat,
            style
        )