"""FastAPI application — serves REST API and static web UI."""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from homeclaw.config import HomeclawConfig

app = FastAPI(title="homeclaw", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_config: HomeclawConfig | None = None


def set_config(config: HomeclawConfig) -> None:
    global _config
    _config = config


def get_config() -> HomeclawConfig:
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


async def require_auth(request: Request) -> None:
    config = get_config()
    if not config.web_password:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.web_password}":
        raise HTTPException(status_code=401, detail="Unauthorized")


AuthDep = Depends(require_auth)

# Mount static files for web UI if dist/ exists
_ui_dist = Path(__file__).parent.parent.parent / "ui" / "dist"
if _ui_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ui_dist / "assets")), name="assets")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(str(_ui_dist / "index.html"))
