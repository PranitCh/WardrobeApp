import os
import cv2
import numpy as np
from django.conf import settings

from wardrobe.ai.models.color_extractor import ColorExtractor

from .color_service import ColorService
from .material_service import MaterialService
from wardrobe.models import ClothingItem


class ClothingService:
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
        extractor = ColorExtractor()

        _, mask = extractor.remove_background(item.image.path)

        preview_dir = os.path.join(settings.MEDIA_ROOT, "previews")
        os.makedirs(preview_dir, exist_ok=True)

        preview_filename = f"{item.id}_preview.png"
        preview_path = os.path.join(preview_dir, preview_filename)

        if mask is not None:
            mask = mask.astype(np.uint8) * 255
            cv2.imwrite(preview_path, mask)

            item.preview_image = f"previews/{preview_filename}"

        return item

    @staticmethod
    def process_item(item):

        import time

        start = time.time()
        ClothingService.create_preview(item)
        print(f"Preview: {time.time() - start:.2f}s")

        start = time.time()
        color_data = ColorService.extract(item.image.path)
        print(f"Color extraction: {time.time() - start:.2f}s")

        start = time.time()
        material_data = MaterialService.predict(item.image.path)
        print(f"Material detection: {time.time() - start:.2f}s")

        # Generate preview
        ClothingService.create_preview(item)

        # Extract color features
        color_data = ColorService.extract(item.image.path)

        item.dominant_colors = color_data["colors_rgb"]
        item.color_percentages = color_data["percentages"]
        item.histogram = color_data["histogram"]

        # Detect material
        material_data = MaterialService.predict(item.image.path)

        item.material = material_data["material"]
        item.weight = material_data["weight"]
        item.breathability = material_data["breathability"]

        item.save()

        return item