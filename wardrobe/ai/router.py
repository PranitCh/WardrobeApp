from fastapi import APIRouter, UploadFile, File
import os
import uuid
import shutil

from wardrobe.ai.services.color_service import ColorService
from wardrobe.ai.services.outfit_service import OutfitService
from wardrobe.ai.services.material_service import MaterialService

router = APIRouter()

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save(file: UploadFile):
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.jpg")
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path

@router.post("/analyze/color")
async def analyze_color(file: UploadFile = File(...)):
    path = save(file)
    return ColorService.extract(path)

@router.post("/analyze/material")
async def analyze_material(file: UploadFile = File(...)):
    path = save(file)
    return MaterialService.predict(path)

@router.post("/analyze/outfit")
async def analyze_outfit(
    top: UploadFile = File(...),
    bottom: UploadFile = File(...)
):
    top_path = save(top)
    bottom_path = save(bottom)

    top_feat = ColorService.extract(top_path)
    bottom_feat = ColorService.extract(bottom_path)

    score = OutfitService.score_pair(top_feat, bottom_feat)

    return {
        "score": score,
        "top_color": top_feat["primary_color"],
        "bottom_color": bottom_feat["primary_color"]
    }