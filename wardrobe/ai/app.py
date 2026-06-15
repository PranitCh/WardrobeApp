from fastapi import FastAPI
from wardrobe.ai.router import router

app = FastAPI(title="Wardrobe AI")

app.include_router(router, prefix="/api")


@app.get("/")
def health():
    return {"status": "ok"}