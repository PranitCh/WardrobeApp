import numpy as np

from wardrobe.ai.models.color_extractor import ColorExtractor

extractor = ColorExtractor()


def remove_background(image_path: str):

    _, mask = extractor.remove_background(image_path)

    return mask.astype(np.uint8).tolist()