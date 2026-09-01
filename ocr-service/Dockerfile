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
# Keep the three large CPU wheels in BuildKit's download cache. curl resumes a
# partial file after a broken connection, so rebuilding does not restart a
# 100-200 MB download from byte zero. Cache mounts are not copied into the
# final image.
RUN --mount=type=cache,target=/var/cache/ocr-wheels \
    download_attempt=0; \
    until curl --fail --location --continue-at - \
               --connect-timeout 30 --speed-limit 1024 --speed-time 600 \
               --output /var/cache/ocr-wheels/paddlepaddle-3.2.2-cp312-cp312-manylinux1_x86_64.whl \
               https://files.pythonhosted.org/packages/7f/2d/f46a5f5464c7d31e9e067e173a449cff8c0d96f7f7282b9454650901fe3c/paddlepaddle-3.2.2-cp312-cp312-manylinux1_x86_64.whl; \
    do \
        download_attempt=$((download_attempt + 1)); \
        [ "$download_attempt" -lt 20 ] || exit 1; \
        sleep 5; \
    done

RUN --mount=type=cache,target=/var/cache/ocr-wheels \
    download_attempt=0; \
    until curl --fail --location --continue-at - \
               --connect-timeout 30 --speed-limit 1024 --speed-time 600 \
               --output /var/cache/ocr-wheels/torch-2.6.0+cpu-cp312-cp312-linux_x86_64.whl \
               https://download.pytorch.org/whl/cpu/torch-2.6.0%2Bcpu-cp312-cp312-linux_x86_64.whl; \
    do \
        download_attempt=$((download_attempt + 1)); \
        [ "$download_attempt" -lt 20 ] || exit 1; \
        sleep 5; \
    done

RUN --mount=type=cache,target=/var/cache/ocr-wheels \
    download_attempt=0; \
    until curl --fail --location --continue-at - \
               --connect-timeout 30 --speed-limit 1024 --speed-time 600 \
               --output /var/cache/ocr-wheels/torchvision-0.21.0+cpu-cp312-cp312-linux_x86_64.whl \
               https://download.pytorch.org/whl/cpu/torchvision-0.21.0%2Bcpu-cp312-cp312-linux_x86_64.whl; \
    do \
        download_attempt=$((download_attempt + 1)); \
        [ "$download_attempt" -lt 20 ] || exit 1; \
        sleep 5; \
    done

# Install the cached large wheels first. The second cache lets pip retain all
# other completed downloads across a failed build without adding its cache to
# the final image. requirements.txt pins the same versions, so pip will not
# download GPU replacements.
RUN --mount=type=cache,target=/var/cache/ocr-wheels \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps \
        /var/cache/ocr-wheels/paddlepaddle-3.2.2-cp312-cp312-manylinux1_x86_64.whl \
        /var/cache/ocr-wheels/torch-2.6.0+cpu-cp312-cp312-linux_x86_64.whl \
        /var/cache/ocr-wheels/torchvision-0.21.0+cpu-cp312-cp312-linux_x86_64.whl \
    && pip install --timeout 600 --retries 10 -r requirements.txt

# Copy only the model-fetching script here.  Its cache is independent from the
# application source, so editing a Python file no longer invalidates either
# model layer below.
COPY scripts/fetch_models.sh /tmp/fetch_models.sh

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
RUN sh /tmp/fetch_models.sh /srv/models \
    && rm /tmp/fetch_models.sh

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

# Keep frequently-changing files at the end of the Dockerfile.  A normal code
# edit now rebuilds only these lightweight COPY layers.
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts

# Drop root: the service only ever reads its own files.
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
