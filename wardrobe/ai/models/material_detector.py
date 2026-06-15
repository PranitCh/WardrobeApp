import torch
import clip
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import cv2
import numpy as np

class MaterialDetector:
    def __init__(self, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = CLIPModel.from_pretrained(
            "openai/clip-vit-base-patch32"
        ).to(self.device)

        self.processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32"
        )

        self.labels = [
            "cotton fabric",
            "denim fabric",
            "wool fabric",
            "linen fabric",
            "polyester fabric",
            "leather material",
            "silk fabric",
            "knit fabric"
        ]

    def predict(self, img):
        """
        img: numpy array (BGR from cv2)
        """

        if img is None:
            raise ValueError("Empty image")

        # BGR → RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # numpy → PIL
        image = Image.fromarray(img).convert("RGB")

        inputs = self.processor(
            text=self.labels,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

            # CLIP similarity scores
            logits = outputs.logits_per_image
            probs = logits.softmax(dim=1).cpu().numpy()[0]

        best_idx = int(probs.argmax())

        return self.labels[best_idx], float(probs[best_idx])
    
MATERIAL_PROPERTIES = {
    "cotton fabric": {"weight": "light", "breathability": "high"},
    "linen fabric": {"weight": "light", "breathability": "high"},
    "denim fabric": {"weight": "heavy", "breathability": "low"},
    "wool fabric": {"weight": "heavy", "breathability": "medium"},
    "polyester fabric": {"weight": "medium", "breathability": "low"},
    "leather material": {"weight": "heavy", "breathability": "low"},
    "silk fabric": {"weight": "light", "breathability": "medium"},
    "knit fabric": {"weight": "medium", "breathability": "medium"},
}