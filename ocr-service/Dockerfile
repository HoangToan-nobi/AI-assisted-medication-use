# CPU image. For GPU, base this on a CUDA runtime image, replace the
# paddlepaddle pin with the matching paddlepaddle-gpu wheel, and set
# OCR_DEVICE=gpu:0. No application code changes are required.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OCR_DEVICE=cpu \
    EAGER_LOAD_OCR=true

# libgomp1  -> paddle's OpenMP runtime
# libgl1 / libglib2.0-0 -> the non-headless OpenCV that paddlex pulls in
# curl -> scripts/fetch_models.sh below (python:3.12-slim does not ship it;
#         without it this build fails at the fetch_models.sh step with "curl: not found")
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Bake the pretrained detection/recognition weights into the image so the
# container starts instantly and needs no network at runtime. These download
# published checkpoints -- they do not train or fine-tune anything.
# Keep the model names in step with app/config.py defaults.
RUN python -c "from paddleocr import PaddleOCR; \
PaddleOCR(lang='vi', device='cpu', enable_mkldnn=True, \
text_detection_model_name='PP-OCRv5_mobile_det', \
text_recognition_model_name='latin_PP-OCRv5_mobile_rec', \
use_doc_orientation_classify=False, use_doc_unwarping=False, \
use_textline_orientation=False)"

# VietOCR: the only model here that can read Vietnamese diacritics. Without it
# the service starts but every accented word comes out wrong, so a failure to
# fetch must break the build rather than surface at runtime.
RUN sh scripts/fetch_models.sh /srv/models

# vgg_transformer's backbone is built on torchvision's OWN pretrained VGG19-BN
# ImageNet weights (~548 MB), fetched from download.pytorch.org the FIRST time
# the predictor is actually constructed -- separate from and in addition to
# the vocr.vn weights fetched above. fetch_models.sh only downloads bytes to a
# file; it never instantiates the model, so this second download was silently
# happening on every cold start instead of at build time (found 2026-08-22
# debugging Modal requests timing out). Construct the predictor once here so
# both downloads are baked into the image and no request ever needs network.
RUN python -c "import torch; \
from vietocr.tool.config import Cfg; \
from vietocr.tool.predictor import Predictor; \
config = Cfg.load_config_from_name('vgg_transformer'); \
config['device'] = 'cpu'; \
config['weights'] = '/srv/models/vgg_transformer.pth'; \
Predictor(config)"

# Drop root: the service only ever reads its own files. Also copy /root/.cache/torch
# (torchvision's VGG19-BN weights baked in above) to /home/appuser/.cache/torch -
# torch resolves its cache dir from $HOME, which becomes /home/appuser once running
# as appuser below; without this copy the baked weights would be invisible at
# runtime and re-downloaded anyway, defeating the point of baking them in.
RUN useradd --create-home --uid 10001 appuser \
    && cp -r /root/.paddlex /home/appuser/.paddlex 2>/dev/null || true \
    && mkdir -p /home/appuser/.cache \
    && cp -r /root/.cache/torch /home/appuser/.cache/torch 2>/dev/null || true \
    && chown -R appuser:appuser /home/appuser /srv
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
