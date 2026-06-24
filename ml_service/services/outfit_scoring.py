from wardrobe.ai.models.outfit_matcher2 import OutfitMatcher


def build_outfit_key(top, bottom, shoe, style):
    shoe_id = shoe["id"] if shoe else "none"
    return f"{top['id']}|{bottom['id']}|{shoe_id}|{style}"


def normalize_rating(rating):
    if rating is None:
        return None
    return 0.45 + ((rating - 1) / 4.0) * 0.5


def build_feature(item):
    color_names = item.get("color_names") or []

    return {
        "colors_rgb": item.get("colors_rgb") or [],
        "percentages": item.get("percentages") or [],
        "primary_color": color_names[0] if color_names else "Unknown",
        "material": item.get("material"),
        "weight": item.get("weight"),
        "breathability": item.get("breathability"),
        "histogram": item.get("histogram") or [],
    }


def score_outfits(
    tops,
    bottoms,
    shoes,
    outfit_type,
    threshold=0.58,
    review_lookup=None,
    review_weight=0.25,
    weather_profile=None,
):
    matcher = OutfitMatcher(use_mask=True, mask_method="rembg")
    raw_results = []
    fallback_results = []
    review_lookup = review_lookup or {}

    if not shoes:
        shoes = [None]

    def infer_clothing_type(item):
        if item.get("weight") == "heavy":
            return "heavy"
        if item.get("weight") == "light":
            return "light"
        return "normal"

    def palette_balance_score(top_feat, bottom_feat, shoe_feat=None):
        colors = [top_feat["primary_color"], bottom_feat["primary_color"]]
        if shoe_feat:
            colors.append(shoe_feat["primary_color"])

        unique_colors = len(set(colors))

        if unique_colors == 3:
            return 0.88
        if unique_colors == 2:
            return 0.72
        return 0.3

    def contrast_score(top_feat, bottom_feat, shoe_feat=None):
        def brightness(rgb):
            r, g, b = rgb
            return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

        top_b = brightness(top_feat["colors_rgb"][0])
        bottom_b = brightness(bottom_feat["colors_rgb"][0])
        diff_tb = abs(top_b - bottom_b)

        if shoe_feat:
            shoe_b = brightness(shoe_feat["colors_rgb"][0])
            diff_ts = abs(top_b - shoe_b)
            diff_bs = abs(bottom_b - shoe_b)
            avg_diff = (diff_tb + diff_ts + diff_bs) / 3.0
        else:
            avg_diff = diff_tb

        if 0.18 <= avg_diff <= 0.55:
            return 0.88
        if 0.10 <= avg_diff < 0.18 or 0.55 < avg_diff <= 0.70:
            return 0.68
        return 0.38

    def diversity_bonus(top_feat, bottom_feat, shoe_feat=None):
        colors = [top_feat["primary_color"], bottom_feat["primary_color"]]
        if shoe_feat:
            colors.append(shoe_feat["primary_color"])

        unique_colors = len(set(colors))
        return 0.08 * (unique_colors - 1)

    def boring_penalty(top_feat, bottom_feat, shoe_feat=None):
        penalty = 0.0
        colors = [top_feat["primary_color"], bottom_feat["primary_color"]]
        if shoe_feat:
            colors.append(shoe_feat["primary_color"])

        if len(set(colors)) == 1:
            penalty += 0.15

        if top_feat["primary_color"] == bottom_feat["primary_color"]:
            penalty += 0.06

        neutral_like = {
            "Black", "White", "Gray", "Light Gray", "Charcoal",
            "Beige", "Cream", "Khaki", "Brown", "Navy",
        }
        if all(c in neutral_like for c in colors):
            penalty += 0.05

        return penalty

    for top in tops:
        top_feat = build_feature(top)
        top_type = infer_clothing_type(top)

        for bottom in bottoms:
            bottom_feat = build_feature(bottom)

            if weather_profile:
                if not weather_profile.get("allow_heavy", True) and top_type == "heavy":
                    continue
                if not weather_profile.get("allow_light", True) and top_type == "light":
                    continue

            best_for_pair = None
            best_passing_for_pair = None

            for shoe in shoes:
                shoe_feat = build_feature(shoe) if shoe else None

                top_bottom_harmony = matcher.calculate_two_item_compatibility(
                    top_feat,
                    bottom_feat,
                )

                if shoe_feat:
                    shoe_match = matcher.calculate_shoe_compatibility(
                        [top_feat["primary_color"], bottom_feat["primary_color"]],
                        shoe_feat,
                        style=outfit_type,
                    )
                    top_shoe_harmony = matcher.calculate_two_item_compatibility(
                        top_feat,
                        shoe_feat,
                    )
                    shoe_component = 0.65 * shoe_match + 0.35 * top_shoe_harmony
                else:
                    shoe_component = 0.0

                palette_component = palette_balance_score(
                    top_feat,
                    bottom_feat,
                    shoe_feat,
                )
                contrast_component = contrast_score(top_feat, bottom_feat, shoe_feat)
                bonus = diversity_bonus(top_feat, bottom_feat, shoe_feat)
                penalty = boring_penalty(top_feat, bottom_feat, shoe_feat)

                if shoe_feat:
                    overall = (
                        0.40 * top_bottom_harmony
                        + 0.20 * shoe_component
                        + 0.15 * palette_component
                        + 0.15 * contrast_component
                        + 0.10 * min(bonus / 0.16, 1.0)
                    ) - penalty
                else:
                    overall = (
                        0.55 * top_bottom_harmony
                        + 0.20 * palette_component
                        + 0.20 * contrast_component
                        + 0.05 * min(bonus / 0.08, 1.0)
                    ) - penalty

                overall = max(0.0, min(overall, 0.95))
                base_score = overall

                if weather_profile:
                    weather_bonus = 0.0

                    if weather_profile.get("prefer_light_colors"):
                        if top_feat["primary_color"] in ["White", "Beige", "Cream"]:
                            weather_bonus += 0.04

                    if weather_profile.get("prefer_dark_colors"):
                        if top_feat["primary_color"] in ["Black", "Blue", "Brown"]:
                            weather_bonus += 0.04

                    if weather_profile.get("rain_mode") and shoe_feat:
                        if shoe_feat["primary_color"] in ["Black", "Brown"]:
                            weather_bonus += 0.04

                    overall = min(0.95, overall + weather_bonus)

                review_score = None
                avg_rating = None
                outfit_key = build_outfit_key(top, bottom, shoe, outfit_type)
                review_data = review_lookup.get(outfit_key)

                if review_data:
                    avg_rating = review_data["avg_rating"]
                    review_score = normalize_rating(avg_rating)
                    overall = (
                        (1 - review_weight) * overall
                        + review_weight * review_score
                    )

                candidate = {
                    "top_id": top["id"],
                    "bottom_id": bottom["id"],
                    "shoe_id": shoe["id"] if shoe else None,
                    "score": overall,
                    "components": {
                        "top_bottom_harmony": round(top_bottom_harmony, 3),
                        "shoe_component": round(shoe_component, 3),
                        "palette_component": round(palette_component, 3),
                        "contrast_component": round(contrast_component, 3),
                        "bonus": round(bonus, 3),
                        "penalty": round(penalty, 3),
                    },
                    "top_color": top_feat["primary_color"],
                    "bottom_color": bottom_feat["primary_color"],
                    "shoe_color": shoe_feat["primary_color"] if shoe_feat else "-",
                    "color_signature": (
                        top_feat["primary_color"],
                        bottom_feat["primary_color"],
                        shoe_feat["primary_color"] if shoe_feat else "-",
                    ),
                    "review_score": review_score,
                    "avg_rating": avg_rating,
                }

                if best_for_pair is None or candidate["score"] > best_for_pair["score"]:
                    best_for_pair = candidate
                if overall >= threshold and (
                    best_passing_for_pair is None
                    or candidate["score"] > best_passing_for_pair["score"]
                ):
                    best_passing_for_pair = candidate

            if best_passing_for_pair is not None:
                raw_results.append(best_passing_for_pair)
            if best_for_pair is not None:
                fallback_results.append(best_for_pair)

    if not raw_results:
        raw_results = fallback_results

    raw_results.sort(key=lambda x: -x["score"])

    diversified = []
    used_tops = {}
    used_bottoms = {}
    used_shoes = {}
    used_color_signatures = {}

    max_per_top = 2
    max_per_bottom = 2
    max_per_shoe = 10
    max_per_color_signature = 1

    for outfit in raw_results:
        top_id = outfit["top_id"]
        bottom_id = outfit["bottom_id"]
        shoe_id = outfit["shoe_id"]
        sig = outfit["color_signature"]

        if used_tops.get(top_id, 0) >= max_per_top:
            continue
        if used_bottoms.get(bottom_id, 0) >= max_per_bottom:
            continue
        if shoe_id and used_shoes.get(shoe_id, 0) >= max_per_shoe:
            continue
        if used_color_signatures.get(sig, 0) >= max_per_color_signature:
            continue

        diversified.append(outfit)

        used_tops[top_id] = used_tops.get(top_id, 0) + 1
        used_bottoms[bottom_id] = used_bottoms.get(bottom_id, 0) + 1
        if shoe_id:
            used_shoes[shoe_id] = used_shoes.get(shoe_id, 0) + 1
        used_color_signatures[sig] = used_color_signatures.get(sig, 0) + 1

    return diversified
