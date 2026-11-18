"""Route Streamlit interactions through the existing FastAPI application in-process."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from backend.app.core.config import Settings
from backend.app.main import create_app
from scripts.seed_data import seed


class Workspace:
    """Treat each Streamlit browser session as a separate synthetic workspace."""

    def __init__(self, settings: Settings | None = None, *, provider=None):
        self._directory = TemporaryDirectory(prefix="eduevidence-streamlit-")
        root = Path(self._directory.name)
        try:
            settings = (settings or Settings.from_environment()).model_copy(update={
                "database_path": root / "workspace.sqlite3",
                "upload_directory": root / "uploads",
            })
            # Seeding initializes a fresh database. No interrupted state needs recovering.
            seed(settings, verbose=False)
            self._app = create_app(settings, provider)
        except Exception:
            self.close()
            raise

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Use production routes, middleware, and structured errors without opening a port."""
        return asyncio.run(self._request(method, path, **kwargs))

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        transport = httpx.ASGITransport(app=self._app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            return await client.request(method, path, **kwargs)

    def close(self):
        self._directory.cleanup()
