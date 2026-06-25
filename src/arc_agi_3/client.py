"""Thin HTTP client for the ARC-AGI-3 REST API.

Ground truth: https://docs.arcprize.org/arc3v1.yaml (OpenAPI 1.0.0).

Notes that bit us if ignored:
- Auth is the `X-API-Key` header, from the ARC-AGI-3 web console (free).
- RESET (and every action) sets `AWSALB*` cookies for session affinity; they
  MUST ride along on subsequent requests. An `httpx.Client` persists cookies
  across calls automatically, so we keep one Client for a whole session.
- `available_actions` come back as integers; `score` is `levels_completed`.
"""

from __future__ import annotations

import os

import httpx

from .structs import Action, FrameData, GameAction

BASE_URL = "https://three.arcprize.org"


class ArcClient:
    def __init__(self, api_key: str | None = None, *, base_url: str = BASE_URL, timeout: float = 30.0):
        self.api_key = api_key or os.getenv("ARC_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "No ARC_API_KEY. Get a free key at https://three.arcprize.org "
                "and put it in .env (ARC_API_KEY=...)."
            )
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
        )

    def __enter__(self) -> "ArcClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- session affinity ------------------------------------------------
    # The API pins a game session to a backend via AWSALB* cookies, which must
    # ride on every later request. Within one process httpx persists them; across
    # CLI invocations we export/import them through the session file.
    def export_cookies(self) -> list[dict]:
        # Iterate the jar (not .items(), which raises on duplicate names like the
        # API's multiple GAMESESSION cookies) and keep domain/path for fidelity.
        return [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            for c in self._http.cookies.jar
        ]

    def import_cookies(self, cookies: list[dict] | None) -> None:
        for c in cookies or []:
            self._http.cookies.set(c["name"], c["value"],
                                   domain=c.get("domain", ""), path=c.get("path", "/"))

    def close(self) -> None:
        self._http.close()

    def _post(self, path: str, body: dict) -> dict:
        r = self._http.post(path, json=body)
        r.raise_for_status()
        return r.json()

    # --- discovery -------------------------------------------------------
    def list_games(self) -> list[dict]:
        """Return [{game_id, title}, ...] for every exposed game."""
        r = self._http.get("/api/games")
        r.raise_for_status()
        return r.json()

    # --- scorecard -------------------------------------------------------
    def open_scorecard(self, *, source_url: str | None = None, tags: list[str] | None = None,
                       opaque: dict | None = None) -> str:
        body: dict = {}
        if source_url:
            body["source_url"] = source_url
        if tags:
            body["tags"] = tags
        if opaque:
            body["opaque"] = opaque
        return self._post("/api/scorecard/open", body)["card_id"]

    def close_scorecard(self, card_id: str) -> dict:
        return self._post("/api/scorecard/close", {"card_id": card_id})

    def get_scorecard(self, card_id: str) -> dict:
        r = self._http.get(f"/api/scorecard/{card_id}")
        r.raise_for_status()
        return r.json()

    # --- game loop -------------------------------------------------------
    def reset(self, *, game_id: str, card_id: str, guid: str | None = None) -> FrameData:
        body: dict = {"game_id": game_id, "card_id": card_id}
        if guid is not None:
            body["guid"] = guid
        return FrameData.from_json(self._post(f"/api/cmd/{GameAction.RESET.path}", body))

    def act(self, action: Action, *, game_id: str, guid: str, card_id: str | None = None) -> FrameData:
        path = f"/api/cmd/{action.kind.path}"
        body = action.payload(game_id=game_id, guid=guid, card_id=card_id)
        return FrameData.from_json(self._post(path, body))
