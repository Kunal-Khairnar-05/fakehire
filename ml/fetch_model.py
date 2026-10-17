"""Build step for deployments: download the released model into models/.

Model files aren't in git. Each promoted model is published as a GitHub Release
(tag "model-v1.2" with model_v1.2.joblib attached), which works as a simple MODEL
REGISTRY: versioned, immutable, downloadable by URL. The deployment says which version
to serve with the MODEL_VERSION environment variable, so rolling forward or back is
"change one variable, redeploy".

    MODEL_VERSION=v1.2 python fetch_model.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = os.getenv("MODEL_REPO", "Kunal-Khairnar-05/fakehire")
VERSION = os.getenv("MODEL_VERSION", "v1.2")
MODELS = Path(__file__).resolve().parent / "models"


def main() -> int:
    file = f"model_{VERSION}.joblib"
    url = f"https://github.com/{REPO}/releases/download/model-{VERSION}/{file}"
    MODELS.mkdir(exist_ok=True)
    print(f"Downloading {url}")
    try:
        urllib.request.urlretrieve(url, MODELS / file)
    except OSError as exc:
        print(f"Model download failed: {exc}", file=sys.stderr)
        return 1      # fail the build: deploying an ml-service without a model is pointless
    # The same pointer file retrain.py writes locally; service/app.py reads it at startup
    (MODELS / "current.json").write_text(json.dumps({"file": file, "version": VERSION}))
    print(f"Ready: {file} ({(MODELS / file).stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
