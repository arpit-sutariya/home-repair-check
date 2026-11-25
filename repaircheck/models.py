"""Local models (free, no API key): CLIP reads the photo, a small text-embedding model reads the description.

Both turn their input into probabilities over the problems in knowledge.json:
- photo: compare the image with written visual cues for each problem ("a brown water stain on a ceiling")
- description: compare the text with each problem's typical symptoms
"""
import io
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps

from . import config, rules

CLIP_IMAGE = "Qdrant/clip-ViT-B-32-vision"
CLIP_TEXT = "Qdrant/clip-ViT-B-32-text"
TEXT_MODEL = "BAAI/bge-small-en-v1.5"


def _norm(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _softmax(x, scale):
    z = scale * (x - x.max())
    e = np.exp(z)
    return e / e.sum()


@lru_cache(maxsize=1)
def _clip():
    from fastembed import ImageEmbedding, TextEmbedding
    cache = str(config.MODEL_CACHE)
    return ImageEmbedding(CLIP_IMAGE, cache_dir=cache), TextEmbedding(CLIP_TEXT, cache_dir=cache)


@lru_cache(maxsize=1)
def _text_model():
    from fastembed import TextEmbedding
    return TextEmbedding(TEXT_MODEL, cache_dir=str(config.MODEL_CACHE))


@lru_cache(maxsize=2)
def _photo_prompts(style: str):
    """style="cues": the visual cues written in knowledge.json (domain knowledge).
    style="names": just "a photo of <problem name>" (the no-knowledge baseline for the eval)."""
    _, text = _clip()
    ids, vecs = [], []
    for issue in rules.knowledge()["issues"]:
        prompts = issue["photo_cues"] if style == "cues" else [f"a photo of {issue['name'].lower()}"]
        vecs.append(_norm(np.mean(_norm(list(text.embed(prompts))), axis=0)))
        ids.append(issue["id"])
    return ids, np.stack(vecs)


@lru_cache(maxsize=1)
def _symptom_vectors():
    issues = rules.knowledge()["issues"]
    texts = [f"{i['name']}: {i['symptoms']}" for i in issues]
    return [i["id"] for i in issues], _norm(list(_text_model().embed(texts)))


def load_image(data: bytes) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((1024, 1024))
    return img


def photo_probs(img: Image.Image, style: str = "cues") -> dict[str, float]:
    image_model, _ = _clip()
    vec = _norm(list(image_model.embed([img]))[0])
    ids, prompts = _photo_prompts(style)
    p = _softmax(prompts @ vec, config.CLIP_SCALE)
    return dict(zip(ids, map(float, p)))


@lru_cache(maxsize=512)
def _query_vector(text: str) -> np.ndarray:
    """Cached: the same description (e.g. an example chip, or a re-check after adding a photo) isn't re-embedded."""
    v = _norm(list(_text_model().embed(["Represent this sentence for searching relevant passages: " + text]))[0])
    v.flags.writeable = False
    return v


def text_probs(text: str) -> dict[str, float]:
    ids, vecs = _symptom_vectors()
    p = _softmax(vecs @ _query_vector(text.strip()), config.TEXT_SCALE)
    return dict(zip(ids, map(float, p)))


def warm():
    _clip(), _photo_prompts("cues"), _symptom_vectors()
    # One throwaway inference each, so ONNX sessions are initialised before the first visitor arrives.
    photo_probs(Image.new("RGB", (224, 224))), text_probs("warm up")
