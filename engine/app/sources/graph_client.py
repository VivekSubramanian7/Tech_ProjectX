"""Microsoft Graph REST client — app-only (client credentials).

Uses msal + httpx directly; no azure-identity or msgraph-sdk to keep the
dependency tree lean (consistent with the torch-free ONNX philosophy).

Env vars consumed (all optional; no network call if unset):
  GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET
  GRAPH_DRIVE_ID      — explicit drive id (used by scan_config)
  GRAPH_USER_ID       — resolve /users/{id}/drive when GRAPH_DRIVE_ID unset
  GRAPH_AUTHORITY     — override authority base (default: https://login.microsoftonline.com)
  GRAPH_BASE_URL      — override Graph v1.0 base  (default: https://graph.microsoft.com/v1.0)
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

_SCOPE = "https://graph.microsoft.com/.default"
_DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
_DEFAULT_BASE_URL = "https://graph.microsoft.com/v1.0"


def has_graph_credentials() -> bool:
    """True iff the three required env vars are all non-empty (no network call)."""
    return bool(
        os.environ.get("GRAPH_TENANT_ID")
        and os.environ.get("GRAPH_CLIENT_ID")
        and os.environ.get("GRAPH_CLIENT_SECRET")
    )


class GraphClient:
    """Thin Graph REST client with token caching and throttle retry.

    Instantiate once per process; it caches the access token and re-acquires
    when it expires.  Thread-safe for concurrent reads (token refresh is
    double-checked behind a simple flag + lock).
    """

    def __init__(self) -> None:
        import threading

        tenant = os.environ["GRAPH_TENANT_ID"]
        client_id = os.environ["GRAPH_CLIENT_ID"]
        client_secret = os.environ["GRAPH_CLIENT_SECRET"]
        authority_base = os.environ.get("GRAPH_AUTHORITY", _DEFAULT_AUTHORITY).rstrip("/")
        self._base_url = os.environ.get("GRAPH_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")

        import msal  # type: ignore[import-untyped]

        self._app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"{authority_base}/{tenant}",
            client_credential=client_secret,
        )
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._lock = threading.Lock()
        self._http = httpx.Client(follow_redirects=True, timeout=60.0)

    # ── Token management ──────────────────────────────────────────────────────

    def _access_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._token_expiry - 60:
            return self._token
        with self._lock:
            now = time.monotonic()
            if self._token and now < self._token_expiry - 60:
                return self._token
            result = self._app.acquire_token_for_client(scopes=[_SCOPE])
            if "access_token" not in result:
                raise RuntimeError(f"MSAL token acquisition failed: {result.get('error_description', result)}")
            self._token = result["access_token"]
            self._token_expiry = now + int(result.get("expires_in", 3600))
        return self._token  # type: ignore[return-value]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "Accept": "application/json",
        }

    # ── HTTP with throttle retry ───────────────────────────────────────────────

    def _get(self, url: str, *, max_retries: int = 5) -> httpx.Response:
        for attempt in range(max_retries):
            resp = self._http.get(url, headers=self._headers())
            if resp.status_code == 429 or resp.status_code == 503:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                time.sleep(min(retry_after, 60))
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"Graph request failed after {max_retries} retries: {url}")

    # ── Drive helpers ──────────────────────────────────────────────────────────

    def resolve_drive_id(self) -> str:
        """Return GRAPH_DRIVE_ID or resolve it via GRAPH_USER_ID → /drive."""
        drive_id = os.environ.get("GRAPH_DRIVE_ID", "").strip()
        if drive_id:
            return drive_id
        user_id = os.environ.get("GRAPH_USER_ID", "").strip()
        if user_id:
            resp = self._get(f"{self._base_url}/users/{user_id}/drive")
        else:
            resp = self._get(f"{self._base_url}/me/drive")
        return resp.json()["id"]

    # ── Delta enumeration ──────────────────────────────────────────────────────

    def iter_delta(
        self,
        drive_id: str,
        token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Page through /drives/{drive_id}/root/delta, return (items, delta_token).

        token=None performs a full enumeration (returns all items in the drive).
        Pass the previously returned delta_token for an incremental run.
        """
        if token:
            url: str = token  # delta tokens ARE URLs
        else:
            url = f"{self._base_url}/drives/{drive_id}/root/delta?$select=id,name,size,lastModifiedDateTime,folder,@microsoft.graph.downloadUrl,deleted"

        items: list[dict[str, Any]] = []
        delta_token: str = ""

        while url:
            resp = self._get(url)
            data = resp.json()
            items.extend(data.get("value", []))
            if "@odata.nextLink" in data:
                url = data["@odata.nextLink"]
            elif "@odata.deltaLink" in data:
                delta_token = data["@odata.deltaLink"]
                url = ""
            else:
                url = ""

        return items, delta_token

    # ── File download ──────────────────────────────────────────────────────────

    def download(self, drive_id: str, item_id: str) -> bytes:
        """Download the raw bytes of a file item."""
        url = f"{self._base_url}/drives/{drive_id}/items/{item_id}/content"
        resp = self._http.get(url, headers=self._headers(), follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    def get_item(self, drive_id: str, item_id: str) -> dict[str, Any]:
        """Fetch metadata for a single item."""
        url = f"{self._base_url}/drives/{drive_id}/items/{item_id}?$select=id,name,size,lastModifiedDateTime,folder"
        return self._get(url).json()
