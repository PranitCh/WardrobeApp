import cv2
from wardrobe.ai.models.material_detector import MaterialDetector, MATERIAL_PROPERTIES

detector = MaterialDetector()


class MaterialService:
    @staticmethod
    def _load_image(image_path: str):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
        return img

    @staticmethod
    def predict(image_path: str):
        img = MaterialService._load_image(image_path)

        material, confidence = detector.predict(img)

        props = MATERIAL_PROPERTIES.get(
            material,
            {"weight": "medium", "breathability": "medium"}
        )

        return {
            "material": material,
            "confidence": float(confidence),
            "weight": props["weight"],
            "breathability": props["breathability"]
        }