"""Static files that can live in two places.

The album artwork is kept in the front end's public folder (frontend/public/static), which is part of the
built site. The server's own folder (backend/static) is checked first, so a file placed there wins."""
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


class FallbackStaticFiles(StaticFiles):
    def __init__(self, *, directory: Path, fallback: Path, **kwargs):
        super().__init__(directory=directory, **kwargs)
        self._fallback = StaticFiles(directory=fallback, check_dir=False)

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
            if response.status_code != 404:
                return response
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        return await self._fallback.get_response(path, scope)  # raises the usual 404 when it is not there either
