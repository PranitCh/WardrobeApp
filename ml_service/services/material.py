import cv2

from wardrobe.ai.models.material_detector import (
    MaterialDetector,
    MATERIAL_PROPERTIES
)

detector = None


def get_detector():
    global detector

    if detector is None:
        detector = MaterialDetector()

    return detector


def predict_material(image_path):
    img = cv2.imread(image_path)

    try:
        material, confidence = get_detector().predict(img)
    except Exception as exc:
        print(f"Material detection unavailable: {exc}")
        material = "unknown"
        confidence = 0.0

    props = MATERIAL_PROPERTIES.get(
        material,
        {
            "weight": "medium",
            "breathability": "medium"
        }
    )

    return {
        "material": material,
        "confidence": float(confidence),
        "weight": props["weight"],
        "breathability": props["breathability"]
    }
