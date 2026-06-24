from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch

from wardrobe.ai.services.clothing_service import ClothingService
from wardrobe.ai.services.outfit_generator_service import OutfitGenerationService
from wardrobe.ai.services.preference_service import PreferenceService
from wardrobe.ai.services.rating_service import RatingService
from wardrobe.ai.services.weather_service import WeatherService
from wardrobe.models import ClothingItem, OutfitRating, UserPreference
from ml_service.services.outfit_scoring import score_outfits


class ClothingServiceTests(TestCase):
    @patch("wardrobe.ai.services.clothing_service.MLClient.analyze")
    def test_process_item_saves_material_when_histogram_is_missing(self, analyze):
        analyze.return_value = {
            "colors": {
                "colors_rgb": [
                    [192, 188, 179],
                    [151, 143, 131],
                    [64, 58, 48],
                ],
                "percentages": [0.7352, 0.1744, 0.0904],
                "color_names": ["Light Gray", "Orange", "Brown"],
                "primary_color": "Light Gray",
            },
            "material": {
                "material": "cotton fabric",
                "confidence": 0.5068897604942322,
                "weight": "light",
                "breathability": "high",
            },
            "style_scores": {
                "casual": 0.31,
                "streetwear": 0.22,
            },
            "bg_removed": True,
        }
        user = User.objects.create_user(
            username="materialuser",
            password="password",
        )
        item = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
        )

        ClothingService.process_item(item)
        item.refresh_from_db()

        self.assertEqual(item.material, "cotton fabric")
        self.assertEqual(item.weight, "light")
        self.assertEqual(item.breathability, "high")
        self.assertEqual(item.color_names, ["Light Gray", "Orange", "Brown"])
        self.assertEqual(
            item.style_scores,
            {
                "casual": 0.31,
                "streetwear": 0.22,
            },
        )
        self.assertEqual(item.histogram, [])
        self.assertTrue(item.ai_processed)

    def test_apply_user_style_choice_promotes_selected_style(self):
        user = User.objects.create_user(
            username="stylechoiceuser",
            password="password",
        )
        item = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
            style_scores={
                "casual": 0.62,
                "streetwear": 0.41,
            },
        )

        ClothingService.apply_user_style_choice(
            item,
            "smart_casual",
        )
        item.refresh_from_db()

        ranked_styles = ClothingService.get_ranked_styles(item)

        self.assertEqual(ranked_styles[0]["slug"], "smart_casual")
        self.assertGreater(
            item.style_scores["smart_casual"],
            item.style_scores["casual"],
        )

    def test_apply_user_style_choices_promotes_up_to_three_styles(self):
        user = User.objects.create_user(
            username="multistylechoiceuser",
            password="password",
        )
        item = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
            style_scores={
                "formal": 0.62,
                "streetwear": 0.41,
            },
        )

        ClothingService.apply_user_style_choices(
            item,
            [
                "sporty_activewear",
                "casual",
                "outdoor_adventure",
            ],
        )
        item.refresh_from_db()

        ranked_slugs = [
            style["slug"]
            for style in ClothingService.get_ranked_styles(item, limit=3)
        ]

        self.assertEqual(
            ranked_slugs,
            [
                "sporty_activewear",
                "casual",
                "outdoor_adventure",
            ],
        )

    def test_apply_user_style_choices_rejects_more_than_three_styles(self):
        user = User.objects.create_user(
            username="toomanystylesuser",
            password="password",
        )
        item = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
        )

        with self.assertRaisesMessage(ValueError, "Select up to 3 styles."):
            ClothingService.apply_user_style_choices(
                item,
                [
                    "sporty_activewear",
                    "casual",
                    "outdoor_adventure",
                    "streetwear",
                ],
            )


class OutfitGenerationServiceTests(TestCase):
    def test_generate_outfits_rejects_items_without_cached_color_features(self):
        user = User.objects.create_user(
            username="testuser",
            password="password",
        )

        ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
        )
        ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
            dominant_colors=[[10, 20, 30]],
            color_percentages=[1.0],
            color_names=["Black"],
        )

        with self.assertRaisesMessage(ValueError, "No AI-processed tops"):
            OutfitGenerationService.generate_outfits(
                user=user,
                style="casual",
            )

    @patch("wardrobe.ai.services.outfit_generator_service.MLClient.score_outfits")
    def test_generate_outfits_uses_remote_scoring_results(self, score_outfits):
        user = User.objects.create_user(
            username="fallbackuser",
            password="password",
        )

        top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
            dominant_colors=[[10, 20, 30]],
            color_percentages=[1.0],
            color_names=["Black"],
            material="cotton",
            breathability="high",
            weight="light",
            histogram=[1.0],
        )
        bottom = ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
            dominant_colors=[[200, 210, 220]],
            color_percentages=[1.0],
            color_names=["White"],
            material="denim",
            breathability="medium",
            weight="medium",
            histogram=[1.0],
        )
        score_outfits.return_value = [
            {
                "top_id": top.id,
                "bottom_id": bottom.id,
                "shoe_id": None,
                "score": 1.42,
                "top_color": "Black",
                "bottom_color": "White",
                "shoe_color": "-",
                "avg_rating": 4,
            }
        ]

        outfits, has_more = OutfitGenerationService.generate_outfits(
            user=user,
            style="casual",
            threshold=0.99,
        )

        self.assertEqual(len(outfits), 1)
        self.assertFalse(has_more)
        self.assertEqual(outfits[0]["top"], top)
        self.assertEqual(outfits[0]["bottom"], bottom)
        self.assertIsNone(outfits[0]["shoe"])
        self.assertEqual(outfits[0]["score"], 0.99)
        self.assertEqual(outfits[0]["user_rating"], 4)
        score_outfits.assert_called_once()

    @patch("wardrobe.ai.services.outfit_generator_service.MLClient.score_outfits")
    def test_generate_outfits_boosts_preferred_colors_and_styles(self, score_outfits):
        user = User.objects.create_user(
            username="preferenceuser",
            password="password",
        )

        top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
            dominant_colors=[[20, 120, 60]],
            color_percentages=[1.0],
            color_names=["Green"],
            material="cotton fabric",
            breathability="high",
            weight="light",
            histogram=[1.0],
        )
        bottom = ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
            dominant_colors=[[40, 80, 140]],
            color_percentages=[1.0],
            color_names=["Blue"],
            material="denim fabric",
            breathability="medium",
            weight="medium",
            histogram=[1.0],
        )
        UserPreference.objects.create(
            user=user,
            color_preferences={"green": 5},
            material_preferences={"denim fabric": 5},
            style_preferences={
                "casual": 3,
                "item:jeans": 5,
            },
        )
        score_outfits.return_value = [
            {
                "top_id": top.id,
                "bottom_id": bottom.id,
                "shoe_id": None,
                "score": 0.5,
                "top_color": "Green",
                "bottom_color": "Blue",
                "shoe_color": "-",
            }
        ]

        outfits, _ = OutfitGenerationService.generate_outfits(
            user=user,
            style="casual",
            threshold=0.0,
        )

        self.assertEqual(outfits[0]["score"], 0.66)
        self.assertAlmostEqual(outfits[0]["preference_bonus"], 0.16)

    @patch("wardrobe.ai.services.outfit_generator_service.MLClient.score_outfits")
    def test_generate_outfits_uses_items_with_requested_style_in_top_four(self, score_outfits):
        user = User.objects.create_user(
            username="stylematchuser",
            password="password",
        )

        top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
            dominant_colors=[[20, 120, 60]],
            color_percentages=[1.0],
            color_names=["Green"],
            breathability="high",
            weight="light",
            histogram=[1.0],
            style_scores={
                "streetwear": 0.35,
                "casual": 0.25,
                "smart_casual": 0.15,
                "business_casual": 0.14,
                "formal": 0.11,
            },
        )
        excluded_top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/excluded_top.jpg",
            dominant_colors=[[200, 200, 200]],
            color_percentages=[1.0],
            color_names=["Gray"],
            breathability="high",
            weight="light",
            histogram=[1.0],
            style_scores={
                "formal": 0.35,
                "business_casual": 0.25,
                "smart_casual": 0.15,
                "party_night_out": 0.14,
                "streetwear": 0.11,
            },
        )
        bottom = ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
            dominant_colors=[[40, 80, 140]],
            color_percentages=[1.0],
            color_names=["Blue"],
            breathability="medium",
            weight="medium",
            histogram=[1.0],
            style_scores={
                "streetwear": 0.4,
                "casual": 0.3,
            },
        )
        score_outfits.return_value = [
            {
                "top_id": top.id,
                "bottom_id": bottom.id,
                "shoe_id": None,
                "score": 0.5,
                "top_color": "Green",
                "bottom_color": "Blue",
                "shoe_color": "-",
            }
        ]

        outfits, _ = OutfitGenerationService.generate_outfits(
            user=user,
            style="streetwear",
            threshold=0.0,
        )

        payload = score_outfits.call_args.args[0]
        top_ids = [
            item["id"]
            for item in payload["tops"]
        ]

        self.assertEqual(outfits[0]["top"], top)
        self.assertIn(top.id, top_ids)
        self.assertNotIn(excluded_top.id, top_ids)

    @patch("wardrobe.ai.services.outfit_generator_service.MLClient.score_outfits")
    def test_generate_outfits_falls_back_when_style_scores_filter_all_tops(self, score_outfits):
        user = User.objects.create_user(
            username="casualfallbackuser",
            password="password",
        )

        top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
            dominant_colors=[[20, 120, 60]],
            color_percentages=[1.0],
            color_names=["Green"],
            breathability="high",
            weight="light",
            histogram=[1.0],
            style_scores={
                "formal": 0.35,
                "business_casual": 0.25,
                "smart_casual": 0.15,
                "party_night_out": 0.14,
                "streetwear": 0.11,
            },
        )
        bottom = ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
            dominant_colors=[[40, 80, 140]],
            color_percentages=[1.0],
            color_names=["Blue"],
            breathability="medium",
            weight="medium",
            histogram=[1.0],
            style_scores={
                "casual": 0.4,
                "streetwear": 0.3,
            },
        )
        score_outfits.return_value = [
            {
                "top_id": top.id,
                "bottom_id": bottom.id,
                "shoe_id": None,
                "score": 0.5,
                "top_color": "Green",
                "bottom_color": "Blue",
                "shoe_color": "-",
            }
        ]

        outfits, _ = OutfitGenerationService.generate_outfits(
            user=user,
            style="casual",
            threshold=0.0,
        )

        payload = score_outfits.call_args.args[0]

        self.assertEqual(outfits[0]["top"], top)
        self.assertEqual(payload["tops"][0]["id"], top.id)


class OutfitScoringTests(TestCase):
    @patch("ml_service.services.outfit_scoring.OutfitMatcher")
    def test_raw_scoring_avoids_perfect_score_saturation(self, matcher):
        matcher.return_value.calculate_two_item_compatibility.return_value = 1.0
        matcher.return_value.calculate_shoe_compatibility.return_value = 1.0

        results = score_outfits(
            tops=[
                {
                    "id": 1,
                    "colors_rgb": [[255, 255, 255]],
                    "percentages": [1.0],
                    "color_names": ["White"],
                    "weight": "light",
                    "breathability": "high",
                }
            ],
            bottoms=[
                {
                    "id": 2,
                    "colors_rgb": [[0, 0, 0]],
                    "percentages": [1.0],
                    "color_names": ["Black"],
                    "weight": "light",
                    "breathability": "high",
                }
            ],
            shoes=[],
            outfit_type="casual",
            threshold=0.0,
            weather_profile={
                "allow_heavy": True,
                "allow_light": True,
                "prefer_light_colors": True,
            },
        )

        self.assertLess(results[0]["score"], 1.0)
        self.assertLessEqual(results[0]["score"], 0.95)


class RatingServiceTests(TestCase):
    def test_preferences_are_built_from_color_names_materials_and_item_styles(self):
        user = User.objects.create_user(
            username="learninguser",
            password="password",
        )
        top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="shirt",
            image="clothes/top.jpg",
            dominant_colors=[[20, 120, 60]],
            color_names=["Green"],
            material="cotton fabric",
        )
        bottom = ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
            dominant_colors=[[40, 80, 140]],
            color_names=["Blue"],
            material="denim fabric",
        )
        OutfitRating.objects.create(
            top_item=top,
            bottom_item=bottom,
            shoe_item=None,
            style="casual",
            generated_score=0.7,
            user_rating=5,
        )

        PreferenceService.update_user_preferences(user)
        prefs = UserPreference.objects.get(user=user)

        self.assertEqual(prefs.color_preferences["green"], 5)
        self.assertEqual(prefs.material_preferences["denim fabric"], 5)
        self.assertEqual(prefs.style_preferences["casual"], 5)
        self.assertEqual(prefs.style_preferences["item:jeans"], 5)

    def test_rating_same_outfit_without_shoes_updates_existing_row(self):
        user = User.objects.create_user(
            username="ratinguser",
            password="password",
        )
        top = ClothingItem.objects.create(
            user=user,
            category="top",
            subcategory="tshirt",
            image="clothes/top.jpg",
        )
        bottom = ClothingItem.objects.create(
            user=user,
            category="bottom",
            subcategory="jeans",
            image="clothes/bottom.jpg",
        )
        OutfitRating.objects.create(
            top_item=top,
            bottom_item=bottom,
            shoe_item=None,
            style="casual",
            generated_score=0.1,
            user_rating=1,
        )
        OutfitRating.objects.create(
            top_item=top,
            bottom_item=bottom,
            shoe_item=None,
            style="casual",
            generated_score=0.2,
            user_rating=2,
        )

        RatingService.save_rating(
            user=user,
            top_id=top.id,
            bottom_id=bottom.id,
            shoe_id="",
            style="casual",
            generated_score="0.8",
            user_rating="2",
        )
        rating = RatingService.save_rating(
            user=user,
            top_id=top.id,
            bottom_id=bottom.id,
            shoe_id="",
            style="casual",
            generated_score="0.9",
            user_rating="5",
        )

        self.assertEqual(OutfitRating.objects.count(), 1)
        rating.refresh_from_db()
        self.assertEqual(rating.generated_score, 0.9)
        self.assertEqual(rating.user_rating, 5)


class WeatherServiceTests(TestCase):
    def test_weather_profile_contains_scoring_flags(self):
        hot_profile = WeatherService.get_weather_profile(
            {
                "temp": 34,
                "weather": "Rain",
            }
        )
        cold_profile = WeatherService.get_weather_profile(
            {
                "temp": 12,
                "weather": "Clear",
            }
        )

        self.assertFalse(hot_profile["allow_heavy"])
        self.assertTrue(hot_profile["allow_light"])
        self.assertTrue(hot_profile["prefer_light_colors"])
        self.assertTrue(hot_profile["rain_mode"])
        self.assertTrue(cold_profile["allow_heavy"])
        self.assertFalse(cold_profile["allow_light"])
        self.assertTrue(cold_profile["prefer_dark_colors"])
