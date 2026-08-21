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

# Drop root: the service only ever reads its own files.
RUN useradd --create-home --uid 10001 appuser \
    && cp -r /root/.paddlex /home/appuser/.paddlex 2>/dev/null || true \
    && chown -R appuser:appuser /home/appuser /srv
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
