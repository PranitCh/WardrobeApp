from fastapi import FastAPI, UploadFile, File
import uvicorn
import uuid
import os

from ml_service.services.color import extract_colors
from ml_service.services.material import predict_material
from ml_service.services.background import remove_background
from ml_service.services.outfit_scoring import score_outfits
from ml_service.services.style import predict_style_scores

app = FastAPI()

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    image_bytes = await file.read()

    file_id = str(uuid.uuid4())
    file_path = os.path.join(TEMP_DIR, f"{file_id}.jpg")

    # save temp file
    with open(file_path, "wb") as f:
        f.write(image_bytes)

    try:
        colors = extract_colors(file_path)
        material = predict_material(file_path)
        style_scores = predict_style_scores(file_path)
        mask = remove_background(file_path)

        return {
            "colors": colors,
            "material": material,
            "style_scores": style_scores,
            "bg_removed": True
        }

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/score-outfits")
async def score_outfit_candidates(payload: dict):
    return {
        "results": score_outfits(
            tops=payload.get("tops", []),
            bottoms=payload.get("bottoms", []),
            shoes=payload.get("shoes", []),
            outfit_type=payload.get("outfit_type", "casual"),
            threshold=payload.get("threshold", 0.58),
            review_lookup=payload.get("review_lookup") or {},
            review_weight=payload.get("review_weight", 0.25),
            weather_profile=payload.get("weather_profile"),
        )
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
