# cached_outfit_generator.py

import os
import pickle
from multiprocessing import Pool
import matplotlib.pyplot as plt
from PIL import Image
from tqdm import tqdm
import cv2
from .color_extractor import ColorExtractor
from .outfit_matcher2 import OutfitMatcher
from .material_detector import MaterialDetector, MATERIAL_PROPERTIES

global_detector = None

def process_and_cache_single(args):

    global global_detector
    if global_detector is None:
        global_detector = MaterialDetector()

    image_path, cache_folder, use_mask, mask_method = args
    extractor = ColorExtractor()
    key = os.path.splitext(os.path.basename(image_path))[0]
    cache_file = os.path.join(cache_folder, key + ".pkl")
    if os.path.exists(cache_file):
        return key
    try:
        hist = extractor.extract_color_histogram(
            image_path, use_mask=use_mask, mask_method=mask_method)
        colors, percentages = extractor.get_dominant_colors(
            image_path, n_colors=3, use_mask=use_mask, mask_method=mask_method)
        color_names = [extractor.get_color_category(*c) for c in colors]

        img = cv2.imread(image_path)

        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        material, confidence = global_detector.predict(img)
        props = MATERIAL_PROPERTIES.get(material, {"weight": "medium", "breathability": "medium"})

        feat = dict(
            histogram=hist,
            colors_rgb=colors,
            percentages=percentages,
            color_names=color_names,
            primary_color=color_names[0],
            material=material,
            material_confidence=float(confidence),
            weight=props["weight"],
            breathability=props["breathability"]
        )
        
        with open(cache_file, 'wb') as f:
            pickle.dump(feat, f)
        return key
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def cache_features_for_folder(image_folder, cache_folder, use_mask=True, mask_method='rembg', n_jobs=6):
    os.makedirs(cache_folder, exist_ok=True)
    files = [os.path.join(image_folder, f) for f in os.listdir(image_folder)
             if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    args = [(img, cache_folder, use_mask, mask_method) for img in files]
    print(f"Starting caching for: {image_folder} ({len(files)} images), using {n_jobs} cores")
    with Pool(processes=n_jobs) as pool:
        results = []
        for res in tqdm(pool.imap_unordered(process_and_cache_single, args), total=len(args), desc=f"Caching {os.path.basename(image_folder)}"):
            results.append(res)
    print(f"Finished caching for {image_folder}. Cached {len([x for x in results if x])} files out of {len(files)}.")

def load_cached_feature(cache_folder, image_filename):
    key = os.path.splitext(os.path.basename(image_filename))[0]
    path = os.path.join(cache_folder, key + ".pkl")
    with open(path, 'rb') as f:
        return pickle.load(f)

##### ---- VISUALIZATION ----- #####

def show_outfit_combination(top_path, bottom_path, shoe_path=None, score=None, style=None):
    imgs = [Image.open(top_path), Image.open(bottom_path)]
    titles = ["Top", "Bottom"]
    if shoe_path and os.path.exists(shoe_path):
        imgs.append(Image.open(shoe_path))
        titles.append("Shoe")

    n = len(imgs)
    plt.figure(figsize=(5 * n, 6))
    for i, (img, title) in enumerate(zip(imgs, titles), 1):
        plt.subplot(1, n, i)
        plt.imshow(img)
        plt.title(title)
        plt.axis('off')
    if score is not None:
        plt.suptitle(f"Outfit ({style}) | Score: {score:.2f}", fontsize=16)
    else:
        plt.suptitle("Outfit", fontsize=16)
    plt.tight_layout()
    plt.show()

##### ---- GENERATE ALL COMBINATIONS ----- #####
def build_outfit_key(top, bottom, shoe, style):
    top_key = os.path.splitext(os.path.basename(top))[0] if top else "none"
    bottom_key = os.path.splitext(os.path.basename(bottom))[0] if bottom else "none"
    shoe_key = os.path.splitext(os.path.basename(shoe))[0] if shoe else "none"
    return f"{top_key}|{bottom_key}|{shoe_key}|{style}"


def normalize_rating(r):
    if r is None:
        return None
    return r / 5.0

def get_cached_combinations(
    tops,
    bottoms,
    shoes,
    top_cache,
    bottom_cache,
    shoe_cache,
    outfit_type,
    threshold=0.58,
    review_lookup=None,
    review_weight=0.25,
    weather_profile=None,
):
    matcher = OutfitMatcher(use_mask=True, mask_method="rembg")
    raw_results = []

    if not shoes:
        shoes = [None]

    def infer_clothing_type(path):
        name = path.lower()
        if any(x in name for x in ["jacket", "hoodie", "sweater"]):
            return "heavy"
        if any(x in name for x in ["short", "tshirt", "tee"]):
            return "light"
        return "normal"

    def palette_balance_score(top_feat, bottom_feat, shoe_feat=None):
        colors = [top_feat["primary_color"], bottom_feat["primary_color"]]
        if shoe_feat:
            colors.append(shoe_feat["primary_color"])

        unique_colors = len(set(colors))

        if unique_colors == 3:
            return 1.0
        elif unique_colors == 2:
            return 0.8
        else:
            return 0.35

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
            return 1.0
        elif 0.10 <= avg_diff < 0.18 or 0.55 < avg_diff <= 0.70:
            return 0.75
        else:
            return 0.45

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
            "Beige", "Cream", "Khaki", "Brown", "Navy"
        }
        if all(c in neutral_like for c in colors):
            penalty += 0.05

        return penalty

    total = len(tops) * len(bottoms) * len(shoes)
    print(f"Scoring {total} outfits with cached features...")

    for top in tqdm(tops, desc="Tops"):
        top_feat = load_cached_feature(top_cache, top)
        top_type = infer_clothing_type(top)

        for bottom in bottoms:
            bottom_feat = load_cached_feature(bottom_cache, bottom)

            if weather_profile:
                if not weather_profile.get("allow_heavy", True) and top_type == "heavy":
                    continue
                if not weather_profile.get("allow_light", True) and top_type == "light":
                    continue

            best_for_pair = None

            for shoe in shoes:
                shoe_feat = load_cached_feature(shoe_cache, shoe) if shoe else None

                top_bottom_harmony = matcher.calculate_two_item_compatibility(top_feat, bottom_feat)

                if shoe_feat:
                    shoe_match = matcher.calculate_shoe_compatibility(
                        [top_feat["primary_color"], bottom_feat["primary_color"]],
                        shoe_feat,
                        style=outfit_type
                    )
                    top_shoe_harmony = matcher.calculate_two_item_compatibility(top_feat, shoe_feat)
                    shoe_component = 0.65 * shoe_match + 0.35 * top_shoe_harmony
                else:
                    shoe_component = 0.0

                palette_component = palette_balance_score(top_feat, bottom_feat, shoe_feat)
                contrast_component = contrast_score(top_feat, bottom_feat, shoe_feat)
                bonus = diversity_bonus(top_feat, bottom_feat, shoe_feat)
                penalty = boring_penalty(top_feat, bottom_feat, shoe_feat)

                if shoe_feat:
                    overall = (
                        0.40 * top_bottom_harmony +
                        0.20 * shoe_component +
                        0.15 * palette_component +
                        0.15 * contrast_component +
                        0.10 * min(bonus / 0.16, 1.0)
                    ) - penalty
                else:
                    overall = (
                        0.55 * top_bottom_harmony +
                        0.20 * palette_component +
                        0.20 * contrast_component +
                        0.05 * min(bonus / 0.08, 1.0)
                    ) - penalty

                overall = max(0.0, min(overall, 1.0))
                base_score = overall

                if weather_profile:
                    weather_bonus = 0.0

                    # hot weather → light colors
                    if weather_profile.get("prefer_light_colors"):
                        if top_feat["primary_color"] in ["White", "Beige", "Cream"]:
                            weather_bonus += 0.1

                    # cold weather → dark colors
                    if weather_profile.get("prefer_dark_colors"):
                        if top_feat["primary_color"] in ["Black", "Blue", "Brown"]:
                            weather_bonus += 0.1

                    # rainy → prefer dark shoes
                    if weather_profile.get("rain_mode") and shoe_feat:
                        if shoe_feat["primary_color"] in ["Black", "Brown"]:
                            weather_bonus += 0.1

                    overall = min(1.0, overall + weather_bonus)

                # === APPLY REVIEW BOOST ===
                review_score = None
                avg_rating = None

                if review_lookup is not None:
                    outfit_key = build_outfit_key(top, bottom, shoe, outfit_type)

                    review_data = review_lookup.get(outfit_key)
                    if review_data:
                        avg_rating = review_data["avg_rating"]
                        review_score = normalize_rating(avg_rating)

                        # simple blend
                        overall = (1 - review_weight) * base_score + review_weight * review_score

                # === FILTER AFTER BLENDING ===
                if overall < threshold:
                    continue

                candidate = {
                    "top": top,
                    "bottom": bottom,
                    "shoe": shoe,
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
                        shoe_feat["primary_color"] if shoe_feat else "-"
                    ),
                    "review_score": review_score,
                    "avg_rating": avg_rating,
                }

                if best_for_pair is None or candidate["score"] > best_for_pair["score"]:
                    best_for_pair = candidate

            if best_for_pair is not None:
                raw_results.append(best_for_pair)

    print(f"Raw analysis complete: {len(raw_results)} best top-bottom combinations >= threshold {threshold:.2f}")

    raw_results.sort(key=lambda x: -x["score"])

    diversified = []
    used_tops = {}
    used_bottoms = {}
    used_shoes = {}
    used_color_signatures = {}

    MAX_PER_TOP = 2
    MAX_PER_BOTTOM = 2
    MAX_PER_SHOE = 10
    MAX_PER_COLOR_SIGNATURE = 1

    for outfit in raw_results:
        top = outfit["top"]
        bottom = outfit["bottom"]
        shoe = outfit["shoe"]
        sig = outfit["color_signature"]

        if used_tops.get(top, 0) >= MAX_PER_TOP:
            continue
        if used_bottoms.get(bottom, 0) >= MAX_PER_BOTTOM:
            continue
        if shoe and used_shoes.get(shoe, 0) >= MAX_PER_SHOE:
            continue
        if used_color_signatures.get(sig, 0) >= MAX_PER_COLOR_SIGNATURE:
            continue

        diversified.append(outfit)

        used_tops[top] = used_tops.get(top, 0) + 1
        used_bottoms[bottom] = used_bottoms.get(bottom, 0) + 1
        if shoe:
            used_shoes[shoe] = used_shoes.get(shoe, 0) + 1
        used_color_signatures[sig] = used_color_signatures.get(sig, 0) + 1

    print(f"Diversified results: {len(diversified)} outfits")
    return diversified

##### ---- MAIN PROGRAM ----- #####

def list_images(folder):
    exts = ('.jpg', '.jpeg', '.png')
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)]

def main():
    # === Set up your wardrobe folders ===
    tops_folder = "/Users/pranit/Documents/Code/Wardrobe App/AI/myward/top"
    bottoms_folder = "/Users/pranit/Documents/Code/Wardrobe App/AI/myward/bottom"
    shoes_folder = "/Users/pranit/Documents/Code/Wardrobe App/AI/myward/shoe"

    # === Set up your cache folders ===
    cache_base = "/Users/pranit/Documents/Code/Wardrobe App/AI/cache"
    top_cache = os.path.join(cache_base, "top")
    bottom_cache = os.path.join(cache_base, "bottom")
    shoe_cache = os.path.join(cache_base, "shoe")

    # === Step 1: Cache features for each item (run once, or when you add new files) ===
    cache_features_for_folder(tops_folder, top_cache, n_jobs=6)
    cache_features_for_folder(bottoms_folder, bottom_cache, n_jobs=6)
    cache_features_for_folder(shoes_folder, shoe_cache, n_jobs=6)

    # === Step 2: Get file lists ===
    tops = list_images(tops_folder)
    bottoms = list_images(bottoms_folder)
    shoes = list_images(shoes_folder)

    # === Step 3: User input ===
    outfit_type = input("Enter outfit type (casual, formal, sporty): ").strip().lower()
    if outfit_type not in ('casual', 'formal', 'sporty'):
        print("Invalid outfit type, using 'casual'.")
        outfit_type = 'casual'

    # === Step 4: Score all combinations with cache ===
    results = get_cached_combinations(
        tops, bottoms, shoes, top_cache, bottom_cache, shoe_cache,
        outfit_type=outfit_type, threshold=0.6)

    # === Step 5: Show top combinations visually =====
    print(f"\nTop recommended {outfit_type} outfits:")
    for idx, r in enumerate(results[:50], 1):  # Show top 10
        top_name = os.path.basename(r['top'])
        bot_name = os.path.basename(r['bottom'])
        shoe_name = os.path.basename(r['shoe']) if r['shoe'] else '-'
        print(f"{idx}. Top: {top_name:25} | Bottom: {bot_name:25} | Shoe: {shoe_name:25} | Score: {r['score']:.2f}")
        show_outfit_combination(r["top"], r["bottom"], r["shoe"], score=r["score"], style=outfit_type)

if __name__ == "__main__":
    main()
