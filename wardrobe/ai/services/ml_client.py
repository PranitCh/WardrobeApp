import os

import requests

ML_BASE_URL = os.environ.get("ML_BASE_URL", "http://localhost:8001")
ML_ANALYZE_URL = os.environ.get("ML_URL", f"{ML_BASE_URL}/analyze")
ML_SCORE_URL = os.environ.get("ML_SCORE_URL", f"{ML_BASE_URL}/score-outfits")


class MLClient:

    @staticmethod
    def analyze(image_path):

        with open(image_path, "rb") as f:

            response = requests.post(
                ML_ANALYZE_URL,
                files={
                    "file": f
                }
            )

        response.raise_for_status()

        return response.json()

    @staticmethod
    def score_outfits(payload):
        response = requests.post(
            ML_SCORE_URL,
            json=payload,
        )

        response.raise_for_status()

        return response.json()["results"]
