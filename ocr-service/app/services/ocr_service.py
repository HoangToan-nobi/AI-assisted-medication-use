"""Text detection (PaddleOCR) + Vietnamese recognition (VietOCR).

Both models are pretrained checkpoints -- there is no training and no
fine-tuning anywhere in this service.

Why two models. PaddleOCR has no Vietnamese recognition model: ``lang="vi"``
resolves to the shared ``latin`` group, whose 836-character dictionary omits
the whole ``U+1EA0-U+1EF9`` block (``ạ ả ấ ầ ậ ắ ẹ ế ệ ị ọ ố ộ ớ ợ ụ ứ ự ...``)
and carries no combining marks. Those characters are outside the model's output
alphabet, so it cannot emit them at any confidence: ``Thuốc`` always comes back
as ``Thuc``, ``Hoạt chất`` as ``Hot cht``. No amount of preprocessing fixes
that. VietOCR's vocabulary covers Vietnamese in full, so it owns recognition;
PaddleOCR owns detection geometry and stays the second opinion on numeric
regions, where VietOCR's built-in language model is prone to inventing words.

The class also absorbs the API differences between PaddleOCR 2.x and 3.x, whose
result shapes are incompatible.
"""

from __future__ import annotations

import logging
import re
import threading
from difflib import SequenceMatcher
from statistics import median
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from PIL import Image

from app.utils.text_utils import strip_diacritics

logger = logging.getLogger(__name__)

# Characters PaddleOCR's latin recognizer physically cannot produce. Their
# presence in a VietOCR reading is proof on its own -- there is nothing to
# arbitrate, because the alternative reading could not have contained them.
_VIETNAMESE_ONLY = re.compile(r"[Ạ-ỹ]")

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
# Trailing \b would not fire after "%" or a digit, so match the unit as a token
# that is not followed by another letter instead.
_UNIT_TOKEN = re.compile(r"(?:mg|mcg|µg|ug|kg|ml|iu|ui|[gl])(?![^\W\d_])", re.IGNORECASE)
_DIGIT_X_DIGIT = re.compile(r"(?<=\d)\s*[x×]\s*(?=\d)")

# Paddle only overrides VietOCR on a non-Vietnamese region when it is clearly
# more confident. The two scores are not calibrated against each other (Paddle
# reports a CTC score, VietOCR a mean per-token probability), so a plain ">"
# would let noise decide. VietOCR is the stronger recognizer here, so it keeps
# the region unless Paddle wins by this margin.
_PADDLE_OVERRIDE_MARGIN = 0.10

# Digits and the symbols that surround them in dosages and dates. A run made
# only of these on both sides is safe to take from PaddleOCR, which reads them
# without a language model second-guessing the glyph.
_FIGURES_ONLY = re.compile(r"[\d+\-*/%.,:=()]+")

# Below this folded-similarity the two readings are not the same text, and
# nothing may be copied between them. See _restore_case for the measurements.
_AGREEMENT_FLOOR = 0.65

# Fewer regions than this and the median says more about noise than about the
# page, so legibility is reported as unknown rather than guessed.
_MIN_AGREEMENT_REGIONS = 8


class OCRUnavailableError(RuntimeError):
    """Raised when the OCR model could not be loaded."""


def confidence_evidence(item: dict[str, Any]) -> float:
    """Best glyph evidence available for deciding whether a region survives.

    The displayed ``confidence`` belongs to the recognizer whose text won. The
    other recognizer can still prove that the region itself is real: a low-prob
    VietOCR reading of ``ĐƠN THUỐC`` must not be discarded when Paddle detected
    the same region at 0.99 but could only spell it ``DON THUC``.
    """
    values = (
        item.get("confidence"),
        item.get("paddle_confidence"),
        item.get("vietocr_confidence"),
    )
    return max(float(value) for value in values if value is not None)


def recognition_agreement(items: Iterable[dict[str, Any]]) -> float | None:
    """How closely PaddleOCR and VietOCR read the same regions. ``None`` if unknown.

    The two recognizers are independent and were both trained on printed text.
    On print they converge: Paddle's reading differs from VietOCR's only by the
    diacritics it cannot emit, which ``_fold`` removes before comparing. On
    handwriting, or on a photo too degraded to read, each model hallucinates
    something different and the similarity collapses.

    Measured over the 65 printed prescriptions in eval/: 64 score a median of
    0.885-1.000, while eval/end2end/don40 -- a 349x336 photo whose OCR returns
    strings like ``CÓNG VIỆN CHO RAY`` -- scores 0.323. The floor lives in that
    gap. Returns ``None`` when VietOCR did not run or too few regions carry
    both readings to judge.
    """
    ratios = [
        SequenceMatcher(
            None,
            OCRService._fold(str(item["paddle_text"])),
            OCRService._fold(str(item["vietocr_text"])),
            autojunk=False,
        ).ratio()
        for item in items
        if item.get("paddle_text") and item.get("vietocr_text")
    ]
    if len(ratios) < _MIN_AGREEMENT_REGIONS:
        return None
    return float(median(ratios))


def filter_ocr_results(
    items: Iterable[dict[str, Any]], threshold: float
) -> list[dict[str, Any]]:
    """Shared production/evaluation confidence gate."""
    return [item for item in items if confidence_evidence(item) >= threshold]


class OCRService:
    """Detects text with PaddleOCR, reads it with VietOCR, returns ``{text, confidence}``.

    Thread-safe for the read path: FastAPI dispatches OCR to a threadpool, and
    neither predictor is guaranteed re-entrant, so inference is serialized
    behind a lock.
    """

    def __init__(
        self,
        lang: str = "en",
        device: str = "cpu",
        model: Any | None = None,
        enable_mkldnn: bool = True,
        ocr_version: str = "PP-OCRv6",
        det_model: str = "",
        rec_model: str = "",
        vietocr_enabled: bool = True,
        vietocr_model: str = "vgg_transformer",
        vietocr_weights: str = "",
        vietocr_batch_size: int = 32,
        torch_threads: int = 0,
        vietocr_predictor: Any | None = None,
    ) -> None:
        self.lang = lang
        self.device = device
        self.enable_mkldnn = enable_mkldnn
        self.ocr_version = ocr_version
        self.det_model = det_model
        self.rec_model = rec_model
        self.vietocr_enabled = vietocr_enabled
        self.vietocr_model = vietocr_model
        self.vietocr_weights = vietocr_weights
        self.vietocr_batch_size = max(1, vietocr_batch_size)
        self.torch_threads = torch_threads
        self._model = model
        self._vietocr_predictor = vietocr_predictor
        self._vietocr_error: str | None = None
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()
        self._load_error: str | None = None

    # -- lifecycle ---------------------------------------------------------

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def load(self) -> None:
        """Instantiate both predictors. Called once from the FastAPI lifespan."""
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    try:
                        self._model = self._build_model()
                        self._load_error = None
                        logger.info(
                            "PaddleOCR detection loaded (lang=%s, device=%s)",
                            self.lang,
                            self.device,
                        )
                    except Exception as exc:  # noqa: BLE001 - reported through /health
                        self._load_error = f"{type(exc).__name__}: {exc}"
                        logger.exception("Failed to load PaddleOCR")
        self._load_vietocr()

    @property
    def vietocr_loaded(self) -> bool:
        return self._vietocr_predictor is not None

    @property
    def vietocr_error(self) -> str | None:
        return self._vietocr_error

    def _load_vietocr(self) -> None:
        """Load VietOCR once. Without it, Vietnamese diacritics cannot be read."""
        if not self.vietocr_enabled or self._vietocr_predictor is not None or self._vietocr_error:
            return
        with self._load_lock:
            if self._vietocr_predictor is not None or self._vietocr_error:
                return
            try:
                import torch
                from vietocr.tool.config import Cfg
                from vietocr.tool.predictor import Predictor

                # Paddle already runs oneDNN across every core. Letting torch do
                # the same makes the two fight for the machine and costs more
                # than the extra threads win back.
                if self.torch_threads > 0:
                    torch.set_num_threads(self.torch_threads)

                # ``Cfg.load_config_from_name`` tải YAML cấu hình từ vocr.vn MỖI LẦN
                # khởi động. Weights đã được nướng sẵn vào image, nhưng bước tải
                # config này thì chưa - nên chỉ cần mất mạng đúng lúc container lên
                # là VietOCR chết, và tệ hơn: lỗi bị nhớ lại (_vietocr_error) nên nó
                # không bao giờ thử lại dù mạng có sau đó. Gặp thật trong lúc đo:
                # service tụt về PaddleOCR latin và đọc "ĐƠN THUỐC" thành "DON THUC".
                local_config = Path(__file__).resolve().parents[1] / "data" / f"{self.vietocr_model}.yml"
                if local_config.is_file():
                    config = Cfg.load_config_from_file(str(local_config))
                else:
                    logger.warning(
                        "Không thấy config VietOCR tại %s; phải tải qua mạng", local_config
                    )
                    config = Cfg.load_config_from_name(self.vietocr_model)
                config["device"] = "cuda:0" if self.device.startswith("gpu") else "cpu"
                # vietocr's downloader caches into tempfile.gettempdir(), so a
                # container re-fetches ~150 MB from vocr.vn on every restart and
                # dies with the upstream host. Prefer a baked-in local file.
                weights = Path(self.vietocr_weights) if self.vietocr_weights else None
                if weights and weights.is_file():
                    config["weights"] = str(weights)
                else:
                    logger.warning(
                        "VietOCR weights not found at %s; falling back to download",
                        self.vietocr_weights or "<unset>",
                    )
                self._vietocr_predictor = Predictor(config)
                logger.info("VietOCR loaded (model=%s)", self.vietocr_model)
            except Exception as exc:  # noqa: BLE001 - reported through /health
                self._vietocr_error = f"{type(exc).__name__}: {exc}"
                logger.error(
                    "VietOCR unavailable -- Vietnamese diacritics will be WRONG, "
                    "because the PaddleOCR fallback cannot represent them: %s",
                    exc,
                )

    def _build_model(self) -> Any:
        from paddleocr import PaddleOCR

        # The three auxiliary models roughly triple cold-start and latency; a
        # photo of a drug box does not need them.
        #
        # enable_mkldnn matters enormously on CPU: a dense drug box takes ~12 s
        # without oneDNN and ~3 s with it. Note that paddlepaddle 3.3.x raises
        # "ConvertPirAttribute2RuntimeAttribute not support ArrayAttribute" as
        # soon as oneDNN is enabled, which is why requirements.txt pins 3.2.x.
        # Set OCR_ENABLE_MKLDNN=false to fall back to the plain CPU kernels.
        optional: dict[str, Any] = {}
        if self.det_model:
            optional["text_detection_model_name"] = self.det_model
        if self.rec_model:
            optional["text_recognition_model_name"] = self.rec_model

        try:
            return PaddleOCR(
                lang=self.lang,
                device=self.device,
                enable_mkldnn=self.enable_mkldnn,
                ocr_version=self.ocr_version,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                **optional,
            )
        except (TypeError, ValueError):
            # PaddleOCR 2.x kwargs.
            return PaddleOCR(
                lang=self.lang,
                use_angle_cls=True,
                use_gpu=self.device.startswith("gpu"),
                show_log=False,
            )
        except Exception:
            # A requested checkpoint may not be cached on a developer machine or
            # may be unavailable offline. Fall back to the smaller cached pair
            # instead of making the API unusable.
            if self.ocr_version not in {"PP-OCRv6", "PP-OCRv5"} and "server" not in f"{self.det_model} {self.rec_model}".lower():
                raise
            logger.warning("%s checkpoint unavailable; falling back to PP-OCRv5", self.ocr_version)
            return PaddleOCR(
                lang=self.lang,
                device=self.device,
                enable_mkldnn=self.enable_mkldnn,
                ocr_version="PP-OCRv5",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
            )

    # -- crop extraction ---------------------------------------------------

    @staticmethod
    def _rectify(image: np.ndarray, poly: Any) -> Image.Image | None:
        """Warp a detected quadrilateral to an upright rectangle.

        A photographed prescription is never axis-aligned, and the previous
        min/max bounding box handed VietOCR slanted text surrounded by
        background. Warping the four detection points instead is the same
        approach PaddleOCR uses internally between detection and recognition.
        """
        try:
            return OCRService._warp(image, poly)
        except (cv2.error, ValueError, TypeError, IndexError):
            # Degenerate geometry must cost one region, not the whole page.
            return None

    @staticmethod
    def _warp(image: np.ndarray, poly: Any) -> Image.Image | None:
        if poly is None or len(poly) < 4:
            return None
        # ``_poly`` may still be an xyxy summary when the page exposed no real
        # polygon; _box_as_points expands that into four corners.
        corners = OCRService._box_as_points(poly)
        if corners is None:
            return None
        points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
        if len(points) != 4:
            # Curved-text polygons carry many points; fall back to their
            # minimum-area rectangle so the warp still has four corners.
            points = cv2.boxPoints(cv2.minAreaRect(points)).astype(np.float32)

        # Order corners clockwise from the top-left so width/height are not
        # transposed for boxes detected in a different point order.
        ordered = np.zeros((4, 2), dtype=np.float32)
        total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
        ordered[0], ordered[2] = points[np.argmin(total)], points[np.argmax(total)]
        ordered[1], ordered[3] = points[np.argmin(diff)], points[np.argmax(diff)]

        width = int(round(max(np.linalg.norm(ordered[0] - ordered[1]),
                              np.linalg.norm(ordered[3] - ordered[2]))))
        height = int(round(max(np.linalg.norm(ordered[0] - ordered[3]),
                               np.linalg.norm(ordered[1] - ordered[2]))))
        if width < 4 or height < 4:
            return None

        # Detection boxes hug the glyphs, which clips the tone marks stacked
        # above Vietnamese vowels -- exactly the signal VietOCR needs. Grow the
        # destination box and let the warp sample the surrounding pixels.
        pad_x, pad_y = max(2, round(width * 0.02)), max(3, round(height * 0.18))
        target_w, target_h = width + 2 * pad_x, height + 2 * pad_y
        destination = np.array(
            [[pad_x, pad_y], [pad_x + width, pad_y],
             [pad_x + width, pad_y + height], [pad_x, pad_y + height]],
            dtype=np.float32,
        )
        warped = cv2.warpPerspective(
            image,
            cv2.getPerspectiveTransform(ordered, destination),
            (target_w, target_h),
            borderMode=cv2.BORDER_REPLICATE,
        )
        return Image.fromarray(warped[:, :, ::-1])

    # -- arbitration -------------------------------------------------------

    @staticmethod
    def _is_numeric_region(text: str) -> bool:
        """True for strengths, counts and codes that carry no real word.

        VietOCR decodes with a Vietnamese language model, which is what makes it
        good at prose and bad at bare figures -- given ``10 x 10`` it will
        happily produce a word. Those regions stay with Paddle.
        """
        stripped = _UNIT_TOKEN.sub("", _DIGIT_X_DIGIT.sub(" ", text))
        return not _LETTER.search(stripped)

    @staticmethod
    def _fold(text: str) -> str:
        """One output character per input character: lowercase, accent-free.

        The 1:1 guarantee is what lets case be copied back by index. Vietnamese
        precomposed characters each decompose to a single base letter, and the
        ``đ``/``Đ`` replacement is also 1:1.
        """
        return "".join((strip_diacritics(char) or char)[0].lower() for char in text)

    @classmethod
    def _restore_case(cls, viet_text: str, paddle_text: str) -> str:
        """Take VietOCR's words, PaddleOCR's capitalization and figures.

        VietOCR owns the letters because it is the only recognizer with the
        Vietnamese alphabet. Everything it is measurably worse at traces to the
        same cause -- it decodes through a language model, where PaddleOCR reads
        glyph shapes. All four repairs below come from real prescriptions:

        * **Case.** ``Nguyễn Thị Hạnh`` read as ``nguyễn thị hạnh``.
        * **Digits.** ``tháng 09`` read as ``tháng 00``.
        * **Symbols.** ``3.5+2g`` read as ``3.5%2g``; ``50/20 mg`` as ``5020mg``.
        * **Row numbers.** ``1.`` read as ``T.`` and ``4.`` as ``A.`` -- which
          silently costs a whole medication, because the row never parses.

        Each repair is bounded so it can only touch figures or capitalization,
        never a word: Paddle's reading of Vietnamese is missing characters by
        construction and must never be copied wholesale.
        """
        folded_viet, folded_paddle = cls._fold(viet_text), cls._fold(paddle_text)
        if len(folded_viet) != len(viet_text) or len(folded_paddle) != len(paddle_text):
            return viet_text  # non-Vietnamese script; indices would not line up
        matcher = SequenceMatcher(None, folded_viet, folded_paddle, autojunk=False)
        # When the two recognizers did not read the same thing, the matcher
        # still finds short coincidental runs, and copying case across them
        # produces interleaved nonsense like "nguyễN Thị hạNh". Measured over
        # the 23 same-region pairs of a real prescription, genuine agreement
        # scored 0.71-1.00 while a deliberately mismatched pair scored 0.55.
        if matcher.ratio() < _AGREEMENT_FLOOR:
            return viet_text

        leading = len(viet_text) - len(viet_text.lstrip())
        pieces: list[str] = []
        for tag, viet_start, viet_end, paddle_start, paddle_end in matcher.get_opcodes():
            viet_run = viet_text[viet_start:viet_end]
            paddle_run = paddle_text[paddle_start:paddle_end]

            if tag == "equal":
                pieces.append(
                    "".join(
                        character.upper()
                        if paddle_text[paddle_start + offset].isupper()
                        else character.lower()
                        if paddle_text[paddle_start + offset].islower()
                        else character
                        for offset, character in enumerate(viet_run)
                    )
                )
            elif tag == "replace":
                pieces.append(
                    cls._better_run(
                        viet_run, paddle_run, viet_start == leading, viet_text, viet_start, viet_end
                    )
                )
            elif tag == "delete":
                pieces.append(viet_run)  # VietOCR saw something Paddle missed
            elif tag == "insert" and cls._is_lost_separator(paddle_text, paddle_start, paddle_end):
                pieces.append(paddle_run)
        return "".join(pieces)

    @staticmethod
    def _is_lost_separator(paddle_text: str, start: int, end: int) -> bool:
        """A single figure separator VietOCR dropped from inside a number.

        ``50/20 mg`` came back as ``5020mg``, which destroys strength
        extraction. Only a lone separator with a digit on each side qualifies,
        so Paddle's stray spaces and punctuation are not pulled in.
        """
        if end - start != 1 or paddle_text[start] not in "/.,+-":
            return False
        return (
            start > 0
            and end < len(paddle_text)
            and paddle_text[start - 1].isdigit()
            and paddle_text[end].isdigit()
        )

    @classmethod
    def _better_run(
        cls, viet_run: str, paddle_run: str, at_start: bool, viet_text: str, viet_start: int, viet_end: int
    ) -> str:
        """Decide one disagreeing run. Defaults to VietOCR."""
        # Pure figures on both sides: Paddle reads them without a language model
        # second-guessing the glyph.
        if (
            len(viet_run) == len(paddle_run)
            and _FIGURES_ONLY.fullmatch(viet_run)
            and _FIGURES_ONLY.fullmatch(paddle_run)
        ):
            return paddle_run
        # A leading row number VietOCR decoded as a letter: `1.` as `T.`, `4.`
        # as `A.`. Paddle spaces the separator differently ("1 ." against "T."),
        # so the runs are compared with its whitespace stripped. Restricted to
        # the very first character, and only when a separator follows it in
        # VietOCR's own reading, so no ordinary word's initial can become a
        # digit. Losing this costs an entire medication: the row never parses.
        if (
            at_start
            and len(viet_run) == 1
            and viet_run.isalpha()
            and paddle_run.strip().isdigit()
            and len(paddle_run.strip()) == 1
            and viet_text[viet_end : viet_end + 1] in {".", ",", ")", "-", " "}
        ):
            return paddle_run.strip()
        # Not repaired here: a unit letter VietOCR decoded as a digit
        # (``Sucralfate 1g`` read as ``19``). A rule that trusts Paddle on any
        # letter/digit swap next to a number also turns a correct ``Viên nén
        # 10`` into ``1O`` when Paddle is the one that misread, and the
        # evidence for it is a single region on a single image. It costs a
        # strength, never a medication, so VietOCR keeps the run.
        return viet_run

    @classmethod
    def _arbitrate(
        cls, paddle_text: str, paddle_conf: float, viet_text: str, viet_prob: float
    ) -> tuple[str, float, str]:
        """Pick the reading for one region. Returns ``(text, confidence, recognizer)``."""
        paddle_text, viet_text = paddle_text.strip(), viet_text.strip()
        if not viet_text:
            return paddle_text, paddle_conf, "paddleocr"
        if not paddle_text:
            return viet_text, viet_prob, "vietocr"

        # Diacritics outrank everything below: Paddle's reading of this region
        # is guaranteed to be missing characters, so no tie-break applies.
        if _VIETNAMESE_ONLY.search(viet_text):
            return cls._restore_case(viet_text, paddle_text), viet_prob, "vietocr"

        # Brand names on prescriptions often carry an alias in parentheses.
        # VietOCR tends to drop the opening bracket and merge the alias into the
        # name, which corrupts a field the resolver depends on. Only safe to
        # prefer Paddle here because the region proved to be diacritic-free.
        if (
            "(" in paddle_text
            and ")" in paddle_text
            and ("(" not in viet_text or viet_text.count(")") > viet_text.count("("))
        ):
            return paddle_text, paddle_conf, "paddleocr"

        if cls._is_numeric_region(paddle_text):
            return paddle_text, paddle_conf, "paddleocr"
        if paddle_conf - viet_prob > _PADDLE_OVERRIDE_MARGIN:
            return paddle_text, paddle_conf, "paddleocr"
        return cls._restore_case(viet_text, paddle_text), viet_prob, "vietocr"

    def _recognize_all(self, image: np.ndarray, items: list[dict[str, Any]]) -> None:
        """Re-read every detected region with VietOCR and arbitrate in place."""
        if self._vietocr_predictor is None:
            return

        crops: list[Image.Image] = []
        indexes: list[int] = []
        for index, item in enumerate(items):
            crop = self._rectify(image, item.get("_poly"))
            if crop is not None:
                crops.append(crop)
                indexes.append(index)
        if not crops:
            return

        # predict_batch buckets by width internally but has no upper bound, so a
        # dense page of same-width regions would build one very large tensor.
        for start in range(0, len(crops), self.vietocr_batch_size):
            chunk = crops[start : start + self.vietocr_batch_size]
            try:
                sentences, probabilities = self._vietocr_predictor.predict_batch(
                    chunk, return_prob=True
                )
            except Exception as exc:  # one bad batch must not fail the page
                logger.warning("VietOCR batch recognition failed: %s", exc)
                continue
            for offset, (sentence, probability) in enumerate(zip(sentences, probabilities)):
                item = items[indexes[start + offset]]
                paddle_text, paddle_conf = str(item["text"]), float(item["confidence"])
                viet_text, viet_prob = str(sentence), round(float(probability), 4)
                text, confidence, recognizer = self._arbitrate(
                    paddle_text, paddle_conf, viet_text, viet_prob
                )
                item["text"] = text
                item["confidence"] = confidence
                item["recognizer"] = recognizer
                # Kept for the eval harness; OCRItem drops them on serialization.
                item["paddle_text"] = paddle_text
                item["vietocr_text"] = viet_text
                item["paddle_confidence"] = round(paddle_conf, 4)
                item["vietocr_confidence"] = viet_prob

    # -- inference ---------------------------------------------------------

    def recognize(self, image: np.ndarray) -> list[dict[str, Any]]:
        """Run OCR on a BGR ndarray, returning one entry per detected region."""
        if self._model is None:
            self.load()
        if self._model is None:
            raise OCRUnavailableError(self._load_error or "OCR model is not loaded.")

        with self._predict_lock:
            if hasattr(self._model, "predict"):
                raw = self._model.predict(image)  # PaddleOCR 3.x
            else:
                raw = self._model.ocr(image, cls=True)  # PaddleOCR 2.x

        items = list(self._parse(raw))
        if self.vietocr_enabled:
            self._load_vietocr()
            with self._predict_lock:
                self._recognize_all(image, items)
        for item in items:
            item.pop("_poly", None)
        return items

    # -- result parsing ----------------------------------------------------

    @staticmethod
    def _parse(raw: Any) -> Iterable[dict[str, Any]]:
        """Normalize both PaddleOCR result shapes into ``{text, confidence}``.

        3.x pages behave like mappings with ``rec_texts`` / ``rec_scores``;
        2.x returns ``[[[box, (text, score)], ...]]``.
        """
        if raw is None:
            return
        pages = raw if isinstance(raw, (list, tuple)) else [raw]
        for page in pages:
            if page is None:
                continue

            texts, scores = OCRService._page_fields(page)
            if texts is not None:
                boxes = OCRService._page_boxes(page)
                polys = OCRService._page_polys(page)
                for index, (text, score) in enumerate(zip(texts, scores or [])):
                    item = {"text": str(text), "confidence": round(float(score), 4)}
                    if boxes is not None and index < len(boxes):
                        item["bbox"] = OCRService._box_as_points(boxes[index])
                    # Recognition crops from the true quadrilateral; the API's
                    # bbox stays whatever geometry field the caller expects.
                    if polys is not None and index < len(polys):
                        item["_poly"] = polys[index]
                    elif item.get("bbox"):
                        item["_poly"] = item["bbox"]
                    yield item
                continue

            # PaddleOCR 2.x: page is a list of [box, (text, score)] rows.
            if isinstance(page, (list, tuple)):
                for row in page:
                    if (
                        isinstance(row, (list, tuple))
                        and len(row) >= 2
                        and isinstance(row[1], (list, tuple))
                        and len(row[1]) >= 2
                    ):
                        yield {
                            "text": str(row[1][0]),
                            "confidence": round(float(row[1][1]), 4),
                            "bbox": OCRService._box_as_points(row[0]),
                            "_poly": row[0],
                        }

    @staticmethod
    def _field(page: Any, key: str) -> Any:
        """Read one field from a 3.x result object, dict or sequence alike."""
        value = getattr(page, key, None)
        if value is None and isinstance(page, dict):
            value = page.get(key)
        if value is None:
            try:
                value = page[key]  # OCRResult supports __getitem__
            except (TypeError, KeyError, IndexError):
                value = None
        return value

    @staticmethod
    def _page_boxes(page: Any) -> Any:
        """Geometry for the API contract: axis-aligned boxes are preferred."""
        for key in ("rec_boxes", "dt_polys", "rec_polys"):
            value = OCRService._field(page, key)
            if value is not None:
                try:
                    return list(value)
                except TypeError:
                    return None
        return None

    @staticmethod
    def _page_polys(page: Any) -> Any:
        """Geometry for cropping: the real quadrilaterals, before flattening.

        Opposite preference to :meth:`_page_boxes` on purpose -- ``rec_boxes``
        is the axis-aligned xyxy summary, which is exactly the information a
        perspective warp needs to avoid.
        """
        for key in ("rec_polys", "dt_polys", "rec_boxes"):
            value = OCRService._field(page, key)
            if value is not None:
                try:
                    return list(value)
                except TypeError:
                    return None
        return None

    @staticmethod
    def _box_as_points(box: Any) -> list[list[float]] | None:
        """Normalize xyxy or polygon geometry for the API contract."""
        try:
            values = np.asarray(box, dtype=float).tolist()
            if len(values) == 4 and all(np.isscalar(value) for value in values):
                x1, y1, x2, y2 = values
                return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            if values and isinstance(values[0], list):
                return [[float(point[0]), float(point[1])] for point in values]
        except (TypeError, ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _page_fields(page: Any) -> tuple[Any, Any]:
        """Extract ``(rec_texts, rec_scores)`` from a 3.x page, if present."""
        for key in ("rec_texts", "rec_score_texts"):
            texts = OCRService._field(page, key)
            if texts is not None:
                return texts, OCRService._field(page, "rec_scores")
        return None, None
