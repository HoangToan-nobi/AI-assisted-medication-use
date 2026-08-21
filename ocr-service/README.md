# Drug OCR Service

A standalone HTTP service that reads a photo of Vietnamese drug packaging or a
prescription and proposes matching rows from a drug database. It is a **separate service**: the
main interaction-checking app calls it over REST and shares no code with it.

The service **proposes candidates only**. It never decides which drug the user
is holding, and its output must not be fed straight into an interaction engine.

---

## Architecture

```text
Image (drug package or prescription; jpg / jpeg / png / webp, <= 10 MB)
  ↓
Image preprocessing        EXIF orientation, resize to <= 1600 px, blur score
  ↓
PaddleOCR detection        PP-OCRv5 mobile det -> text region polygons
  ↓
Perspective rectification  each quadrilateral warped upright before reading
  ↓
VietOCR recognition        vgg_transformer, batched; the only model here that
                           can produce Vietnamese diacritics
  ↓
Arbitration                VietOCR wins accented text, PaddleOCR keeps bare
                           figures; capitalization, dosage separators and row
                           numbers are repaired from PaddleOCR
  ↓
Raw OCR text               per-region text + confidence, kept verbatim
  ↓
Text normalization         unicode, punctuation, whitespace, line breaks
  ↓
Strength / ingredient extraction
  ↓
Drug Resolver              RapidFuzz over line-window candidates
  ↓
Vietnam Drug DB            app/data/drugs.csv (swappable)
  ↓
Document routing            package = one drug; prescription = one row per drug
  ↓
Top 3 candidates per drug   weighted name + strength + ingredient score
  ↓
User confirmation          requires_confirmation is always true
```

### Why two OCR models

PaddleOCR has no Vietnamese recognition model. `lang="vi"` resolves to its
shared `latin` group, and that recognizer's character dictionary holds 836
entries with no codepoint anywhere in `U+1EA0`–`U+1EF9`:

```
ả ạ ắ ằ ẳ ẵ ặ ấ ầ ẩ ẫ ậ ẻ ẽ ẹ ế ề ể ễ ệ ỏ ọ ố ồ ổ ỗ ộ
ớ ờ ở ỡ ợ ủ ụ ứ ừ ử ữ ự ỉ ị ỳ ỷ ỹ ỵ
```

It carries no combining marks either, so those characters are outside the
model's output alphabet — it cannot emit them at any confidence, on any image.
`Thuốc` can only ever come back as `Thuc`, `Hoạt chất` as `Hot cht`. The
larger `PP-OCRv6_medium_rec` (18 708 entries) has the same gap. No amount of
preprocessing, upscaling or contrast work changes this.

VietOCR's vocabulary covers Vietnamese in full, so it owns recognition.
PaddleOCR stays for what it is good at. VietOCR decodes through a Vietnamese
language model, which is exactly why it reads prose better and figures worse;
PaddleOCR reads glyph shapes and has no such bias. So four things are repaired
from Paddle's reading, each bounded so it can never rewrite a word — all four
are real failures seen on real prescriptions:

| Repair | Observed |
|---|---|
| Capitalization | `Nguyễn Thị Hạnh` read as `nguyễn thị hạnh` |
| Digits | `tháng 09` read as `tháng 00` |
| Symbols | `3.5+2g` as `3.5%2g`; `50/20 mg` as `5020mg` |
| Row numbers | `1.` as `T.`, `4.` as `A.` — each costs a whole medication |

Nothing is copied when the two readings disagree too much to be the same text
(folded similarity below 0.65), because the matcher would otherwise splice
coincidental fragments together.

Measured on `eval/`:

| Config | CER | Line accuracy | CER, accented lines | Accuracy, accented lines |
|---|---|---|---|---|
| PaddleOCR alone | 11.8 % | 9.1 % | 12.6 % | **0.0 %** |
| PaddleOCR + VietOCR | **0.0 %** | **100 %** | **0.0 %** | **100 %** |

Not one line containing a Vietnamese tone mark was ever read correctly by
PaddleOCR alone — that is what a missing alphabet looks like, as opposed to a
model that is merely inaccurate. Reproduce with `scripts/eval_ocr.py`; note
that `eval/` holds clean synthetic renders, so these are best-case numbers.
Re-measure on real photographs before quoting them.

### There is no training and no fine-tuning

The service loads published PaddleOCR and VietOCR checkpoints and runs
inference. Nothing in this repository trains, fine-tunes, distils or otherwise
modifies a model, and there is no training data, no optimiser and no
checkpoint-writing code.

No LLM, no OpenAI API and no external OCR API are used. All inference is local.

---

## Requirements

* Ubuntu 20.04+ (built and tested on Ubuntu 24.04)
* Python 3.10+ (tested on 3.12)
* ~4 GB disk for PaddlePaddle, torch, and the downloaded OCR weights
* CPU only by default

## Setup (Ubuntu)

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libgomp1 libgl1 libglib2.0-0

cd drug-ocr-service
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Fetch the VietOCR checkpoint into models/ (~150 MB, published weights).
sh scripts/fetch_models.sh
```

`scripts/fetch_models.sh` is not optional. Without `models/vgg_transformer.pth`
the service still starts and still answers, but no Vietnamese diacritic can be
read — check `vietocr_loaded` on `/health` before trusting any output. The
script is also run at Docker build time so a container never needs the network.

The first server start downloads the pretrained PaddleOCR detection and
recognition models into `~/.paddlex/`. Later starts are offline. Both models
are loaded once per worker, not once per request.

### Production model and cost

Everything runs locally, so there is no per-image API bill. The application still needs a machine to run inference;
"zero cost" means no external OCR charge, not zero hosting cost. For a small
CPU deployment, use one Uvicorn worker and a request queue. For higher traffic,
run several workers or GPU replicas and keep the model loaded in each worker.

Useful settings:

```bash
# Default: mobile detection. ~1.9 s on a drug box, ~6.2 s on a photographed
# A4 prescription with 45 text regions.
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Server-tier detection: 1.8x slower, no measured accuracy gain on either.
# Worth re-testing if your images are harder than the ones this was tuned on.
OCR_DET_MODEL=PP-OCRv5_server_det \
  uvicorn app.main:app --host 0.0.0.0 --port 8000

# GPU production server
OCR_DEVICE=gpu:0 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`OCR_VIETOCR_ENABLED=false` exists only for latin-only deployments. It does not
degrade results gracefully — it makes every accented word wrong.

## Run the server

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

* Swagger UI: <http://localhost:8000/docs>
* ReDoc: <http://localhost:8000/redoc>
* OpenAPI JSON: <http://localhost:8000/openapi.json>

## Streamlit demo

Run the API in one terminal, then run the demo UI in another:

```bash
source .venv/bin/activate
streamlit run demo_streamlit.py
```

Open <http://localhost:8501>, upload a medicine package or prescription, and
click **Phân tích ảnh**. The UI calls the same REST endpoint as the future
frontend. Set `OCR_API_URL` if the API is running elsewhere:

```bash
OCR_API_URL=http://192.168.1.20:8000 streamlit run demo_streamlit.py
```

For development with auto-reload, skip the startup model load so restarts stay
fast (the model then loads lazily on the first OCR request):

```bash
EAGER_LOAD_OCR=false uvicorn app.main:app --reload --port 8000
```

---

## API

### `GET /health`

```bash
curl -s http://localhost:8000/health
```

```json
{
  "status": "ok",
  "ocr_model_loaded": true,
  "drug_database_loaded": true,
  "drug_count": 30,
  "ocr_error": null,
  "vietocr_loaded": true,
  "vietocr_error": null
}
```

`ocr_model_loaded` is `false` with a populated `ocr_error` if detection failed
to load; the process still starts so the failure is observable rather than a
crash loop.

`vietocr_loaded` is reported separately and matters just as much: when it is
`false`, requests still succeed but every Vietnamese diacritic in the response
is wrong, because the PaddleOCR fallback has no codepoint for those characters.
Treat it as a hard failure in monitoring.

### `POST /api/v1/ocr` — OCR only

```bash
curl -s -X POST http://localhost:8000/api/v1/ocr \
  -F "image=@/path/to/drug.jpg"
```

```json
{
  "success": true,
  "raw_text": "HAPACOL 650\nParacetamol 650mg\nDHG PHARMA",
  "normalized_text": "HAPACOL 650\nParacetamol 650mg\nDHG PHARMA",
  "ocr_results": [
    { "text": "HAPACOL 650",       "confidence": 0.9991 },
    { "text": "Paracetamol 650mg", "confidence": 0.9914 },
    { "text": "DHG PHARMA",        "confidence": 0.9999 }
  ],
  "metadata": {
    "blur_score": 3599.31,
    "width": 760, "height": 420,
    "original_width": 760, "original_height": 420,
    "image_format": "PNG",
    "processing_time_ms": 1502.4
  }
}
```

`blur_score` is Laplacian variance. Blurry images are **not** rejected; the
score is returned so the frontend can warn ("ảnh hơi mờ, chụp lại?"). As a rough
guide, under ~100 tends to look blurry, but the useful threshold depends on the
camera, so tune it against real uploads.

### `POST /api/v1/drug/recognize` — OCR + resolve

```bash
curl -s -X POST http://localhost:8000/api/v1/drug/recognize \
  -F "image=@/path/to/drug.jpg"
```

```json
{
  "success": true,
  "raw_text": "AUGMENTIN 625mg\nAmoxicillin 500 mg\nClavulanic acid 125 mg",
  "normalized_text": "AUGMENTIN 625mg\nAmoxicillin 500 mg\nClavulanic acid 125 mg",
  "document_type": "medicine_package",
  "ocr_results": [{ "text": "AUGMENTIN 625mg", "confidence": 0.998 }],
  "detected_information": {
    "strengths": ["625 mg", "500 mg", "125 mg"],
    "possible_ingredients": ["Clavulanic acid", "Amoxicillin"]
  },
  "candidates": [
    {
      "drug_id": "6",
      "drug_name": "Augmentin 625",
      "active_ingredient": "Amoxicillin + Clavulanic acid",
      "strength": "500 mg + 125 mg",
      "dosage_form": "Tablet",
      "manufacturer": "GSK",
      "registration_number": "VN-20326-17",
      "score": 0.9536,
      "score_breakdown": {
        "name_score": 0.93, "strength_score": 1.0, "ingredient_score": 1.0
      }
    }
  ],
  "status": "high_confidence",
  "requires_confirmation": true,
  "metadata": {
    "blur_score": 2914.7,
    "width": 760, "height": 420,
    "original_width": 760, "original_height": 420,
    "image_format": "PNG",
    "ocr_time_ms": 1383.9,
    "resolver_time_ms": 1.9,
    "total_time_ms": 1385.8
  }
}
```

The same endpoint also accepts a prescription screenshot. OCR regions include
their `bbox` coordinates, and a document with markers such as `ĐƠN THUỐC`,
`THÔNG TIN BỆNH NHÂN` and `CÁCH DÙNG` is classified as `prescription`. Numbered
rows are then resolved independently. The response keeps the legacy top-level
`candidates` field (empty for a prescription) and adds `medications`:

```json
{
  "document_type": "prescription",
  "medications": [
    {
      "row_number": 1,
      "ocr_text": "1 Methyl prednisolon Medrol 4mg ...",
      "detected_information": {"strengths": ["4 mg"], "possible_ingredients": []},
      "candidates": [{"drug_name": "Medrol 4mg", "score": 0.95}],
      "requires_confirmation": true
    }
  ],
  "candidates": [],
  "requires_confirmation": true
}
```

If a prescription has no usable OCR geometry, the service falls back to
numbered OCR lines. For best results, each medication should have a visible
row number and the database must contain the exact brand/strength; a missing
database row cannot be recovered by OCR or fuzzy matching.

`status` follows the thresholds in `app/config.py`:

| Top score | `status`            | Suggested frontend behaviour                       |
| --------- | ------------------- | -------------------------------------------------- |
| >= 0.90   | `high_confidence`   | Preselect the top candidate, still ask to confirm.  |
| >= 0.75   | `medium_confidence` | Show all three, ask the user to pick.               |
| < 0.75    | `uncertain`         | "Không nhận diện chắc chắn. Vui lòng chụp lại hoặc nhập tên thuốc." |

`requires_confirmation` is pinned to `true` by the response schema in every
case, including a perfect 1.0 score.

### Errors

No traceback is ever returned. Failures use one shape:

```json
{
  "success": false,
  "error": { "code": "INVALID_IMAGE", "message": "Uploaded file is not a valid image." }
}
```

| Code             | HTTP | Cause                                                   |
| ---------------- | ---- | ------------------------------------------------------- |
| `INVALID_IMAGE`  | 400  | Not decodable, or not jpg/jpeg/png/webp                 |
| `FILE_TOO_LARGE` | 413  | Over `MAX_FILE_SIZE_BYTES` (10 MB)                      |
| `OCR_UNAVAILABLE`| 503  | Model failed to load                                    |
| `INTERNAL_ERROR` | 500  | Anything else (details go to the server log only)       |

---

## Configuration

Everything is environment-driven; defaults are in `app/config.py`.

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `MAX_FILE_SIZE_BYTES` | `10485760` | Upload limit (10 MB) |
| `MAX_IMAGE_DIMENSION` | `1600` | Longest side after resize; aspect ratio preserved |
| `OCR_LANG` | `vi` | PaddleOCR language group. Affects detection only — its recognizer cannot read Vietnamese either way |
| `OCR_DEVICE` | `cpu` | `cpu` or e.g. `gpu:0`; applies to both models |
| `OCR_CONFIDENCE_THRESHOLD` | `0.5` | Regions below this are dropped |
| `OCR_ENABLE_MKLDNN` | `true` | oneDNN CPU acceleration (~4x). Needs paddlepaddle 3.2.x |
| `OCR_DET_MODEL` | `PP-OCRv5_mobile_det` | Detection model. `PP-OCRv5_server_det` is ~2x slower for no measured gain |
| `OCR_REC_MODEL` | `latin_PP-OCRv5_mobile_rec` | Paddle recognition; only arbitrates bare figures and capitalization |
| `OCR_VIETOCR_ENABLED` | `true` | Turning this off makes every Vietnamese diacritic wrong |
| `OCR_VIETOCR_MODEL` | `vgg_transformer` | VietOCR checkpoint name |
| `OCR_VIETOCR_WEIGHTS` | `models/vgg_transformer.pth` | Local weights; avoids vietocr's /tmp download on every restart |
| `OCR_VIETOCR_BATCH_SIZE` | `32` | Crops per `predict_batch` call |
| `OCR_TORCH_THREADS` | `min(8, cpu_count)` | Torch threads; capped so it does not contend with Paddle's oneDNN |
| `DRUGS_CSV_PATH` | `app/data/thuoc_final_project.csv` | Drug database file |
| `MAX_CANDIDATES` | `3` | Candidates returned |
| `SHORTLIST_SIZE` | `200` | Rows reranked with the expensive scorer |
| `MAX_LINE_WINDOW` | `3` | Consecutive OCR lines joined into one candidate |
| `WEIGHT_NAME` | `0.65` | Name weight in the final score |
| `WEIGHT_STRENGTH` | `0.20` | Strength weight |
| `WEIGHT_INGREDIENT` | `0.15` | Ingredient weight |
| `DRUG_HIGH_CONFIDENCE` | `0.90` | `high_confidence` threshold |
| `DRUG_MEDIUM_CONFIDENCE` | `0.75` | `medium_confidence` threshold |
| `EAGER_LOAD_OCR` | `true` | Load the model at startup instead of first request |

### Switching to GPU

No architectural change is needed:

```bash
pip uninstall -y paddlepaddle
pip install paddlepaddle-gpu   # matching your CUDA version
export OCR_DEVICE=gpu:0
```

`OCRService` passes `device` straight through to PaddleOCR, so nothing else
moves.

---

## How matching works

**1. Candidate phrases.** Brand names are often split across OCR regions, so
every run of 1–3 consecutive lines becomes a candidate phrase:

```text
["HAPAC0L", "65O"]  ->  "HAPAC0L", "65O", "HAPAC0L 65O"
```

**2. OCR confusion folding.** Rather than guessing which character OCR meant,
confusable characters are folded to one representative (`0`→`o`, `1`/`l`→`i`,
`5`→`s`, `8`→`b`) on **both** sides of every comparison:

```text
"HAPAC0L 65O"  ->  "hapacoi 6so"
"Hapacol 650"  ->  "hapacoi 6so"   ->  exact match
```

Vietnamese tone marks are folded away in the same step. OCR reads "Hạ sốt" as
"Ha söt" and "huyết" as "huyét", which costs 5-23 points of similarity against
a correctly-accented database purely from marks that identify nothing:

```text
"Long huyét P/H extra" vs "Long huyết P/H extra"   ->  95 before, 100 after
"Giam dau - Ha söt"    vs "Giảm đau - Hạ sốt"      ->  77 before, 100 after
```

The raw OCR string is never rewritten — `raw_text` and `normalized_text` are
both returned so the frontend can show what was actually read, accents intact.

**3. Two-stage retrieval.** A cheap `ratio` + `token_set_ratio` pass scores the
whole database, then only the top `SHORTLIST_SIZE` rows are reranked with
`WRatio` blended with `ratio`. `WRatio` alone awards a flat 95 to *any*
substring containment, which ties "Augmentin 625" with "Augmentin 1g"; the
length-sensitive `ratio` breaks that tie. Doing the expensive scorer on every
row costs ~160 ms at 44k rows, versus ~42 ms for the two-stage version.

**4. Combined score.**

```text
final = name_score       * 0.65
      + strength_score   * 0.20
      + ingredient_score * 0.15
```

* `strength_score` is the fraction of the doses *printed on the pack* that the
  row actually has, read from both the `strength` column and the drug name
  (Vietnamese brand names usually encode the dose). This is what makes a pack
  reading `625 mg` rank `Augmentin 625` above `Augmentin 1g`, and a pack reading
  `875 mg + 125 mg` rank them the other way round. When the photo shows no
  strength at all the score is a neutral 0.25 rather than 0.
* `ingredient_score` is the fraction of the row's ingredients that literally
  appear in the OCR text. It also lets a smudged brand name still be found —
  rows whose full ingredient set is present are added to the shortlist even if
  the name scored badly.

Every candidate carries its `score_breakdown`, so a surprising ranking can be
explained without re-running anything.

---

## Drug database

`app/data/drugs.csv` is **sample data** (30 common Vietnamese products) for
development and tests. Schema:

```csv
id,drug_name,active_ingredient,strength,dosage_form,manufacturer,registration_number
1,Hapacol 650,Paracetamol,650 mg,Tablet,DHG Pharma,VD-24537-16
```

### Updating `drugs.csv`

1. Edit the file, keeping the header row and the seven columns.
2. `id` must be unique; leave it blank and the row number is used.
3. Put combination ingredients and strengths in the same order, separated by
   `+`: `Amoxicillin + Clavulanic acid` with `500 mg + 125 mg`.
4. Include the dose in `drug_name` when the pack shows it there
   (`Augmentin 625`) — the resolver reads strengths from both fields.
5. Restart the service. The database is read and indexed once at startup.

To point at a different file without editing anything:

```bash
DRUGS_CSV_PATH=/data/thuoc.csv uvicorn app.main:app --port 8000
```

`app/data/thuoc_final_project.csv` (43,970 rows from the Vietnamese drug
registry) is included as a realistic example. It uses the registry's own
`Ten_thuoc,Hoat_chat_list` layout, which the loader detects and adapts
automatically:

```bash
DRUGS_CSV_PATH=app/data/thuoc_final_project.csv uvicorn app.main:app --port 8000
```

### Moving to PostgreSQL

`DrugResolver` depends on the `DrugRepository` protocol — anything with
`load() -> list[Drug]`. Swapping the storage engine touches neither the
resolver's scoring nor `OCRService`:

```python
class PostgresDrugRepository:
    def load(self) -> list[Drug]:
        return [Drug(**row) for row in cursor.fetchall()]

drug_resolver = DrugResolver(PostgresDrugRepository())
```

---

## Tests

```bash
source .venv/bin/activate
pytest -q                 # 89 tests, ~1 s
pytest -v                 # per-test names
```

PaddleOCR **and VietOCR are mocked everywhere** in the suite
(`tests/conftest.py`), so tests never download or load a model and the whole
run takes about a second. Both the 2.x and 3.x PaddleOCR result shapes are
covered by fakes, as is `Predictor.predict_batch`. Tests that are not about
recognition pass `vietocr_enabled=False` so `recognize()` cannot reach for the
real 150 MB checkpoint.

Coverage includes the required cases:

* health endpoint, invalid file, oversized file, OCR response schema
* a client filename of `innocent.png` on non-image bytes is still rejected
* normalization of OCR errors, the `0/O 1/I/l 5/S 8/B` fold, and Vietnamese
  tone-mark folding (including `đ`, which NFD alone does not decompose)
* strength extraction for `500 mg`, `650mg`, `125 mg/5 ml`, `10 mg/ml`, `0.5%`,
  `1000 IU`, and the regression where `HAPAC0L` was read as "0 litres"
* `"HAPAC0L 65O"` → `Hapacol 650` as the top candidate
* `"AUGMENTlN 625 mg"` ranks `Augmentin 625` above `Augmentin 1g`, and the
  reverse case where the pack reads `875 mg`
* resolver latency under 100 ms, including on a synthetic 40k-row database
* recognizer arbitration: diacritics beat a more confident Paddle reading, bare
  figures stay with Paddle, capitalization is copied only across stretches the
  two recognizers agree on, and a VietOCR crash still returns the page
* `raw_text` carries the arbitrated reading on both endpoints — a regression
  guard for the bug where it preferred the diacritic-free `paddle_text`

### Accuracy evaluation

The unit suite proves the wiring; it cannot tell you whether OCR got better.
`scripts/eval_ocr.py` measures that against ground truth:

```bash
python scripts/eval_ocr.py eval/                    # all three configurations
python scripts/eval_ocr.py eval/ --config hybrid    # just the current pipeline
```

Each `eval/<name>.png` needs an `eval/<name>.txt` holding the expected text,
one line per detected region. Lines are matched to predictions by similarity
before scoring, since detection order is not something the recognizer controls.
The script reports CER and whole-line accuracy overall and separately for lines
containing `U+1EA0`–`U+1EF9`.

`eval/` currently holds synthetic renders, which is the easy case. **Populate it
with real photographs before trusting the numbers** — images are gitignored, so
nothing patient-identifying is committed by accident.

### Drug-matching evaluation

Separate from OCR on purpose: recognition errors and ranking errors have
different fixes, and one end-to-end number hides which of the two moved.

```bash
python scripts/eval_match.py            # eval/drug_match.csv
python scripts/eval_match.py --verbose  # every row, not just the failures
```

`eval/drug_match.csv` holds `source,ocr_line,expected` — the OCR text of one
medication row and the database name that should come back first. Use
`__NOT_IN_DB__` when the drug is genuinely absent: correct behaviour there is a
refusal, so those rows are scored on confidence rather than on a name, and a
confident answer counts as a *false match* — the worst outcome available,
because it proposes a medicine the patient was never prescribed.

---

## Docker

```bash
docker build -t drug-ocr-service .
docker run -p 8000:8000 drug-ocr-service
```

Then `curl http://localhost:8000/health`.

The build bakes the pretrained weights into the image, so the container starts
without network access. To use your own database, mount over the CSV:

```bash
docker run -p 8000:8000 \
  -v /path/to/thuoc.csv:/srv/app/data/drugs.csv:ro \
  drug-ocr-service
```

---

## Performance

Measured on an idle 20-core CPU, at the accuracy-first defaults:

| Stage | Target | Measured |
| ----- | ------ | -------- |
| Detection, `PP-OCRv5_mobile_det` | — | ~1.0 s |
| VietOCR recognition, ~9 regions batched | — | ~0.9 s |
| Drug resolver (30 rows) | < 100 ms | ~2 ms |
| Drug resolver (44k rows) | < 100 ms | ~42 ms |
| **Total, `eval/` renders (9 regions)** | < 6 s | **~1.9 s** |
| **Total, real photo (45 regions)** | < 6 s | **~6.2 s** |

Cost scales with the number of detected regions, and a photographed A4
prescription has far more of them than a drug box. The `server_det` tier costs
1.8x more (11.2 s on the same photo) and found exactly the same six
medications, which is why it is not the default. On a GPU (`OCR_DEVICE=gpu:0`)
both models move together with no code change.

VietOCR is cheaper than it looks because `predict_batch` buckets crops by width
and runs them as one tensor: on the full prescription it read 9 regions in
0.82 s, against 5.6 s for the PaddleOCR pipeline it replaced.

### Three settings do almost all of that work

The first two were chosen by measurement on a real 1920x1080 photo of a
Panadol Extra box that originally took **12.5 s**:

| Configuration | Busy box |
| ------------- | -------- |
| paddlepaddle 3.3.1, oneDNN off (forced by the crash below) | 12 600 ms |
| paddlepaddle 3.2.2, oneDNN on, default `medium` models | 3 160 ms |
| paddlepaddle 3.2.2, oneDNN on, `PP-OCRv5_mobile` models | **630 ms** |

* **oneDNN** is worth ~4x on CPU. paddlepaddle 3.3.x cannot use it at all --
  it raises `ConvertPirAttribute2RuntimeAttribute not support` on every model
  tier -- which is why `requirements.txt` pins 3.2.2. Re-test before raising it.
* **The detection tier** is the main latency dial; see the table above.
* **`OCR_TORCH_THREADS`** is capped at 8. Paddle's oneDNN already spreads
  across every core, and letting torch do the same makes the two contend.

Cost scales with the **number of text regions**, not image size: a full drug
box has 30-40 regions, a plain one has 4.

Notes:


* The model loads once at startup (~1.4 s) and is reused; it is never reloaded
  per request.
* OCR is CPU-bound, so both endpoints run it via
  `starlette.concurrency.run_in_threadpool` and never block the event loop.
  Inference itself is serialized behind a lock, because one PaddleOCR predictor
  is not re-entrant.
* Uploads are streamed in 64 KB chunks and rejected as soon as they pass the
  size limit. Images are held in memory only, and never written to disk.

## Security

* Only `jpg`, `jpeg`, `png` and `webp` are accepted, decided by **decoding the
  bytes**, not by the client's filename or `Content-Type`.
* Uploads are capped at 10 MB, and Pillow's decompression-bomb guard is set.
* Uploaded bytes are never executed, never written to disk, and never logged.
* Tracebacks are logged server-side and never returned to the client.
* The container runs as a non-root user.

## Scope

This service does OCR and candidate generation, and nothing else. It contains
no interaction-checking logic, and it never selects a final drug — the user
confirms a candidate, and only that confirmed choice should reach the
interaction engine.
