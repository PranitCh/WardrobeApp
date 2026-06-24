import cv2
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from wardrobe.ai.style_options import STYLE_OPTIONS


class StyleDetector:
    def __init__(self, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = CLIPModel.from_pretrained(
            "openai/clip-vit-base-patch32"
        ).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32"
        )
        self.labels = [
            (slug, f"a {label.lower()} clothing outfit")
            for slug, label in STYLE_OPTIONS
        ]

    def predict_scores(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(img).convert("RGB")
        prompts = [prompt for _slug, prompt in self.labels]

        inputs = self.processor(
            text=prompts,
            images=image,
            return_tensors="pt",
            padding=True,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1).cpu().numpy()[0]

        return {
            slug: float(probs[index])
            for index, (slug, _prompt) in enumerate(self.labels)
        }


detector = None


def get_detector():
    global detector

    if detector is None:
        detector = StyleDetector()

    return detector


def predict_style_scores(image_path):
    try:
        return get_detector().predict_scores(image_path)
    except Exception as exc:
        print(f"Style detection unavailable: {exc}")
        return {}

