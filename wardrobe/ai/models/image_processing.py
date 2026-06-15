from PIL import Image, ImageFilter
import numpy as np
import os

def create_blurred_background_preview(image_path, mask_bool, output_path):
    original = Image.open(image_path).convert("RGBA")

    # blurred background
    blurred = original.filter(ImageFilter.GaussianBlur(radius=12))

    # mask → PIL format
    mask = (mask_bool.astype("uint8") * 255)
    mask_img = Image.fromarray(mask, mode="L").filter(ImageFilter.GaussianBlur(2))

    # combine sharp clothing + blurred background
    result = Image.composite(original, blurred, mask_img)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.save(output_path)

    print("Mask stats:", np.unique(mask))

    return output_path