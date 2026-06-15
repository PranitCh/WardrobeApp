import numpy as np
import cv2
import matplotlib.pyplot as plt
from PIL import Image
from .color_extractor import ColorExtractor


class OutfitMatcher:
    """
    Enhanced matcher that can handle complete outfits including:
    - Tops (shirts, t-shirts, jackets)
    - Bottoms (pants, skirts, shorts)
    - Shoes (sneakers, boots, sandals, dress shoes)
    - Optional: Accessories
    """
    
    def __init__(self, use_mask=True, mask_method='rembg'):
        self.extractor = ColorExtractor()
        self.use_mask = use_mask
        self.mask_method = mask_method
        
        self.complementary_pairs = {
            "Red": ["Green", "Cyan"],
            "Orange": ["Blue"],
            "Yellow": ["Purple", "Blue"],
            "Green": ["Red", "Pink"],
            "Cyan": ["Red", "Orange"],
            "Blue": ["Orange", "Yellow"],
            "Purple": ["Yellow"],
            "Pink": ["Green"],
            "Brown": ["Blue", "Green", "Cream"]
        }
        
        self.neutral_colors = ["White", "Gray", "Black", "Beige", "Cream", "Brown"]
        
        self.shoe_color_rules = {
            "formal": {
                "best": ["Black", "Brown", "Gray"],
                "acceptable": ["White", "Blue"],
                "avoid": ["Red", "Orange", "Yellow", "Pink"]
            },
            "casual": {
                "best": ["White", "Black", "Gray", "Brown"],
                "acceptable": ["Blue", "Red", "Green"],
                "avoid": []
            },
            "sporty": {
                "best": ["White", "Black", "Gray"],
                "acceptable": ["Red", "Blue", "Green", "Orange"],
                "avoid": ["Brown"]
            }
        }
    
    def calculate_histogram_similarity(self, hist1, hist2):
        similarity = cv2.compareHist(
            hist1.astype(np.float32), 
            hist2.astype(np.float32), 
            cv2.HISTCMP_CORREL
        )
        return similarity
    
    def are_colors_complementary(self, color1_name, color2_name):
        return color2_name in self.complementary_pairs.get(color1_name, [])
    
    def is_neutral(self, color_name):
        return color_name in self.neutral_colors
    
    def extract_item_colors(self, image_path):
        hist = self.extractor.extract_color_histogram(
            image_path, 
            use_mask=self.use_mask,
            mask_method=self.mask_method
        )
        colors, percentages = self.extractor.get_dominant_colors(
            image_path, 
            n_colors=3,
            use_mask=self.use_mask,
            mask_method=self.mask_method
        )
        
        color_categories = [self.extractor.get_color_category(*c) for c in colors]
        
        return {
            'histogram': hist,
            'colors_rgb': colors,
            'colors_names': color_categories,
            'percentages': percentages,
            'primary_color': color_categories[0]
        }
    
    def calculate_two_item_compatibility(self, item1_info, item2_info):
        hist_sim = self.calculate_histogram_similarity(
            item1_info['histogram'], 
            item2_info['histogram']
        )
        hist_score = (hist_sim + 1) / 2
        
        harmony_score = 0
        total_weight = 0
        
        colors1 = item1_info['colors_rgb']
        colors2 = item2_info['colors_rgb']
        pct1 = item1_info['percentages']
        pct2 = item2_info['percentages']

        # --- MATERIAL COMPATIBILITY ---
        item1_weight = item1_info.get("weight", "medium")
        item2_weight = item2_info.get("weight", "medium")

        item1_breath = item1_info.get("breathability", "medium")
        item2_breath = item2_info.get("breathability", "medium")

        material_score = 0

        # --- WEIGHT SCORING (improved) ---

        if item1_weight == item2_weight:
            material_score += 0.2

        elif (item1_weight == "light" and item2_weight == "medium") or \
            (item1_weight == "medium" and item2_weight == "light"):
            material_score += 0.15   # 👈 GOOD combo

        elif (item1_weight == "medium" and item2_weight == "heavy") or \
            (item1_weight == "heavy" and item2_weight == "medium"):
            material_score += 0.1    # 👈 acceptable

        elif (item1_weight == "light" and item2_weight == "heavy") or \
            (item1_weight == "heavy" and item2_weight == "light"):
            material_score -= 0.1    # 👈 only slight penalty

        # --- BREATHABILITY SCORING ---

        if item1_breath == item2_breath:
            material_score += 0.15

        elif (item1_breath == "high" and item2_breath == "medium") or \
            (item1_breath == "medium" and item2_breath == "high"):
            material_score += 0.1

        elif (item1_breath == "high" and item2_breath == "low") or \
            (item1_breath == "low" and item2_breath == "high"):
            material_score -= 0.1

        # Add to final harmony (scaled)
        harmony_score += material_score

        
        for c1, p1 in zip(colors1, pct1):
            cat1 = self.extractor.get_color_category(*c1)
            for c2, p2 in zip(colors2, pct2):
                cat2 = self.extractor.get_color_category(*c2)
                weight = p1 * p2
                total_weight += weight
                
                # Stronger reduction of neutral preference
                if self.is_neutral(cat1) and self.is_neutral(cat2):
                    harmony_score += 0.15 * weight
                elif self.is_neutral(cat1) or self.is_neutral(cat2):
                    harmony_score += 0.35 * weight
                elif self.are_colors_complementary(cat1, cat2):
                    harmony_score += 1.0 * weight
                elif cat1 == cat2:
                    harmony_score += 0.70 * weight
                else:
                    harmony_score += 0.50 * weight
        
        if total_weight > 0:
            harmony_score = harmony_score / total_weight
        else:
            harmony_score = 0.5
        
        final_score = (
            0.25 * hist_score +
            0.65 * harmony_score +
            0.1 * material_score
        )

        print("MATERIAL DEBUG:",
        item1_weight, item2_weight,
        item1_breath, item2_breath)

        return final_score
    
    def calculate_shoe_compatibility(self, outfit_colors, shoe_info, style="casual"):
        shoe_color = shoe_info['primary_color']
        
        rules = self.shoe_color_rules.get(style, self.shoe_color_rules['casual'])
        if shoe_color in rules['best']:
            base_score = 0.9
        elif shoe_color in rules['acceptable']:
            base_score = 0.7
        elif shoe_color in rules['avoid']:
            base_score = 0.3
        else:
            base_score = 0.6
        
        color_match_bonus = 0
        for outfit_color in outfit_colors:
            if shoe_color == outfit_color:
                color_match_bonus += 0.15
            elif self.is_neutral(shoe_color) or self.is_neutral(outfit_color):
                color_match_bonus += 0.1
            elif self.are_colors_complementary(shoe_color, outfit_color):
                color_match_bonus += 0.05
        
        color_match_bonus = min(color_match_bonus, 0.2)
        
        final_score = min(base_score + color_match_bonus, 1.0)
        return final_score
    
    def analyze_complete_outfit(self, 
        top_path, 
        bottom_path, 
        shoes_path=None, 
        style="casual",
        top_meta=None,
        bottom_meta=None,
        shoes_meta=None):
        top_info = self.extract_item_colors(top_path)
        bottom_info = self.extract_item_colors(bottom_path)

        if top_meta:
            top_info.update(top_meta)

        if bottom_meta:
            bottom_info.update(bottom_meta)
        
        top_bottom_score = self.calculate_two_item_compatibility(top_info, bottom_info)
        
        report = {
            'style': style,
            'top_colors': top_info['colors_names'],
            'bottom_colors': bottom_info['colors_names'],
            'top_bottom_score': top_bottom_score,
            'top_bottom_rating': self._get_rating(top_bottom_score),
            'items_analyzed': ['top', 'bottom']
        }
        
        if shoes_path:
            shoes_info = self.extract_item_colors(shoes_path)
            outfit_colors = [top_info['primary_color'], bottom_info['primary_color']]
            
            shoes_score = self.calculate_shoe_compatibility(
                outfit_colors, shoes_info, style
            )
            
            report['shoes_colors'] = shoes_info['colors_names']
            report['shoes_score'] = shoes_score
            report['shoes_rating'] = self._get_rating(shoes_score)
            report['items_analyzed'].append('shoes')
            
            overall_score = (
                0.4 * top_bottom_score +
                0.35 * shoes_score +
                0.25 * self.calculate_two_item_compatibility(top_info, shoes_info)
            )
        else:
            overall_score = top_bottom_score
        
        # Calculate primary colors list
        primary_colors = [
            top_info['primary_color'],
            bottom_info['primary_color']
        ]
        if shoes_path:
            primary_colors.append(shoes_info['primary_color'])
        
        # Debug prints to understand color variety
        print("Primary Colors:", primary_colors)
        print("Top-Bottom Score:", top_bottom_score)
        
        # Diversity bonus for different colors
        unique_colors = len(set(primary_colors))
        diversity_bonus = 0.1 * (unique_colors - 1)  # +0.1 for each different color after the first
        overall_score += diversity_bonus
        print("Diversity Bonus:", diversity_bonus)
        
        # Penalize all neutral outfits harshly
        if all(self.is_neutral(color) for color in primary_colors):
            overall_score = 0.2
            print("All neutral colors detected - applying harsh penalty.")
        
        overall_score = min(max(overall_score, 0.0), 1.0)
        
        print("Final Overall Score:", overall_score)
        
        report['overall_score'] = overall_score
        report['overall_rating'] = self._get_rating(overall_score)
        report['recommendation'] = self._generate_recommendation(report)
        
        return report
    
    def _get_rating(self, score):
        if score >= 0.85:
            return "Excellent"
        elif score >= 0.70:
            return "Very Good"
        elif score >= 0.55:
            return "Good"
        elif score >= 0.40:
            return "Fair"
        else:
            return "Poor"
    
    def _generate_recommendation(self, report):
        overall = report['overall_score']
        style = report['style']
        
        recommendations = []
        
        if overall >= 0.75:
            recommendations.append(f"✓ Great {style} outfit! The colors work well together.")
        elif overall >= 0.60:
            recommendations.append(f"→ Decent {style} look. Minor adjustments could improve it.")
        else:
            recommendations.append(f"✗ This combination needs work for a {style} outfit.")
        
        if report['top_bottom_score'] < 0.50:
            recommendations.append("• Consider changing either the top or bottom for better color harmony.")
        
        if 'shoes' in report['items_analyzed']:
            if report['shoes_score'] < 0.50:
                recommendations.append(f"• Shoe color doesn't match well with this {style} outfit. Consider neutral shoes.")
            elif report['shoes_score'] >= 0.80:
                recommendations.append("• Shoes are a perfect match!")
        
        return " ".join(recommendations)
    
    def visualize_outfit(self, top_path, bottom_path, shoes_path=None, style="casual"):
        report = self.analyze_complete_outfit(top_path, bottom_path, shoes_path, style)
        
        items = []
        titles = []
        colors = []
        
        if self.use_mask and self.mask_method == 'rembg':
            top_img, _ = self.extractor.remove_background(top_path)
        else:
            top_img = Image.open(top_path)
        items.append(top_img)
        titles.append('Top')
        colors.append(report['top_colors'])
        
        if self.use_mask and self.mask_method == 'rembg':
            bottom_img, _ = self.extractor.remove_background(bottom_path)
        else:
            bottom_img = Image.open(bottom_path)
        items.append(bottom_img)
        titles.append('Bottom')
        colors.append(report['bottom_colors'])
        
        if shoes_path:
            if self.use_mask and self.mask_method == 'rembg':
                shoes_img, _ = self.extractor.remove_background(shoes_path)
            else:
                shoes_img = Image.open(shoes_path)
            items.append(shoes_img)
            titles.append('Shoes')
            colors.append(report['shoes_colors'])
        
        n_items = len(items)
        fig = plt.figure(figsize=(6*n_items, 10))
        gs = fig.add_gridspec(3, n_items, height_ratios=[3, 0.5, 1.5], hspace=0.3)
        
        for i, (item, title, item_colors) in enumerate(zip(items, titles, colors)):
            ax = fig.add_subplot(gs[0, i])
            ax.imshow(item)
            ax.set_title(f'{title}\n{", ".join(item_colors[:2])}', fontsize=12, fontweight='bold')
            ax.axis('off')
        
        ax_scores = fig.add_subplot(gs[1, :])
        ax_scores.axis('off')
        
        score_text = f"Top ↔ Bottom: {report['top_bottom_score']:.2f} ({report['top_bottom_rating']})"
        if 'shoes' in report['items_analyzed']:
            score_text += f"  |  Shoes Match: {report['shoes_score']:.2f} ({report['shoes_rating']})"
        
        ax_scores.text(0.5, 0.5, score_text, ha='center', va='center',
                      fontsize=13, fontweight='bold',
                      bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
        
        ax_analysis = fig.add_subplot(gs[2, :])
        ax_analysis.axis('off')
        
        analysis_text = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  OUTFIT ANALYSIS - {style.upper()} STYLE                                      
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Overall Score: {report['overall_score']:.2f}/1.00                           
║  Overall Rating: {report['overall_rating']}                                   
║                                                                               
║  Recommendation:                                                              
║  {report['recommendation'][:75]}
║  {report['recommendation'][75:150] if len(report['recommendation']) > 75 else ''}
╚═══════════════════════════════════════════════════════════════════════════════╝
        """
        ax_analysis.text(0.5, 0.5, analysis_text, ha='center', va='center',
                        fontfamily='monospace', fontsize=11,
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        plt.suptitle(f'{style.title()} Outfit Compatibility Analysis', 
                    fontsize=16, fontweight='bold', y=0.98)
        plt.tight_layout()
        plt.show()


# Example usage
if __name__ == "__main__":
    matcher = OutfitMatcher(use_mask=True, mask_method='rembg')
    
    top_path = "/Users/pranit/Documents/Code/Wardrobe App/AI/archive/images_compressed/data/T-Shirt/0add1694-17d0-46ec-a9fc-900da252af41.jpg"
    bottom_path = "/Users/pranit/Documents/Code/Wardrobe App/AI/archive/images_compressed/data/Pants/0c224954-0e0f-4caa-82c8-cf9581e89336.jpg"
    #shoes_path = "/Users/pranit/Documents/Code/Wardrobe App/AI/archive/images_compressed/data/Shoes/0fd66046-0879-42ab-be2e-a919c8a82aab.jpg"  # Optional
    
    try:
        print("=== Analyzing Complete Outfit ===\n")
        
        report = matcher.analyze_complete_outfit(
            top_path, 
            bottom_path, 
            None,  # Or shoes_path if available
            style="casual"
        )
        
        print("Primary Colors:", report['top_colors'][0], report['bottom_colors'][0],
              report.get('shoes_colors', ['N/A'])[0])
        print(f"Overall Score: {report['overall_score']:.2f}")
        print(f"Overall Rating: {report['overall_rating']}")
        print("Recommendation:", report['recommendation'])
        
        print("\nGenerating visual analysis...")
        matcher.visualize_outfit(top_path, bottom_path, None, style="casual")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
