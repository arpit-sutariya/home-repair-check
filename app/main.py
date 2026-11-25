import base64
import binascii
import json
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from repaircheck import config, diagnose as dx, models, pros, rules

STATIC = Path(__file__).parent / "static"
EVAL_RESULTS = config.ROOT / "eval" / "results" / "latest.json"
_ready = threading.Event()
_rate: dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()
_SWEEP_ABOVE = 5000  # forget idle visitors once this many are tracked, so memory can't grow without bound


def _warm():
    if config.WARM_MODELS:
        models.warm()
    _ready.set()


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(title="Home Repair Check", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/evals", include_in_schema=False)
def evals_page():
    return FileResponse(STATIC / "evals.html")


@app.get("/api/meta")
def meta():
    on = dx.claude_available()
    return {"locations": list(dx.LOCATIONS), "engine": "claude" if on else "local",
            "model": config.MODEL if on else None, "contacts_source": pros.source(), "ready": _ready.is_set() or not config.WARM_MODELS,
            "problems": [{"id": i["id"], "name": i["name"]} for i in rules.knowledge()["issues"]]}


@app.get("/api/evals")
def evals():
    if not EVAL_RESULTS.exists():
        raise HTTPException(404, "No eval results yet. Run: python -m eval.run_eval")
    return json.loads(EVAL_RESULTS.read_text())


def _visitor(request: Request) -> str:
    # Behind one proxy (Render, Fly, a load balancer) the LAST X-Forwarded-For entry is the address the proxy
    # saw. Earlier entries are whatever the client sent, so using the first one let anyone dodge the limit.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(visitor: str):
    now = time.time()
    with _rate_lock:
        if len(_rate) > _SWEEP_ABOVE:
            for k in [k for k, q in _rate.items() if not q or now - q[-1] > config.RATE_WINDOW_S]:
                del _rate[k]
        q = _rate[visitor]
        while q and now - q[0] > config.RATE_WINDOW_S:
            q.popleft()
        if len(q) >= config.RATE_LIMIT:
            retry = int(config.RATE_WINDOW_S - (now - q[0])) + 1
            raise HTTPException(429, "Too many checks in a short time. Please wait a few minutes.",
                                headers={"Retry-After": str(retry)})
        q.append(now)


def _decode(data_url: str | None) -> bytes | None:
    if not data_url:
        return None
    b64 = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    if len(b64) > config.MAX_PHOTO_BYTES * 4 // 3 + 16:
        raise HTTPException(413, "That photo is too large (max 8 MB).")
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "That doesn't look like an image.")


class DiagnoseIn(BaseModel):
    image: str | None = None
    text: str = Field("", max_length=5000)
    location: str | None = Field(None, max_length=60)


@app.post("/api/diagnose")
def diagnose(body: DiagnoseIn, request: Request):
    _rate_limit(_visitor(request))
    image = _decode(body.image)
    if not _ready.wait(timeout=120):
        raise HTTPException(503, "The AI models are still starting up. Please try again in a minute.",
                            headers={"Retry-After": "30"})
    try:
        return dx.diagnose(image, body.text, body.location)
    except dx.InputError as e:
        raise HTTPException(400, str(e))
    except (OSError, ValueError):
        raise HTTPException(400, "Couldn't open that photo. Please try a JPG or PNG.")


class QuoteIn(BaseModel):
    issue_id: str = Field(max_length=60)
    text: str = Field("", max_length=5000)
    amount: float = Field(gt=0, lt=10_000_000)


@app.post("/api/quote")
def quote(body: QuoteIn):
    issue = rules.issues().get(body.issue_id)
    if not issue:
        raise HTTPException(404, "Unknown problem type")
    return rules.quote_verdict(body.amount, rules.costs(issue, body.text), structural=issue["structural"])


class ProsIn(BaseModel):
    issue_id: str = Field(max_length=60)
    place: str | None = Field(None, max_length=120)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)


@app.post("/api/pros")
def find_pros(body: ProsIn, request: Request):
    """Real repair businesses near the customer for the trades this problem needs (see repaircheck/pros.py)."""
    _rate_limit("pros:" + _visitor(request))
    if body.issue_id not in rules.issues():
        raise HTTPException(404, "Unknown problem type")
    try:
        return pros.find(body.issue_id, body.place, body.lat, body.lon)
    except pros.LookupFailed as e:
        raise HTTPException(502, f"{e}. Please try again in a moment.")
