#!/usr/bin/env python3
"""Utility script for ingesting MedHub API resources into pandas DataFrames.

The script authenticates with MedHub using the OAuth client credentials flow,
retrieves paginated results for one or more endpoints, and materialises the
payloads as pandas DataFrames. Optionally, the resulting DataFrames can be
persisted to disk in CSV/Parquet/JSON formats.

Environment variables (fallbacks for CLI flags):
    MEDHUB_BASE_URL         MedHub API base URL, e.g. https://api.medhub.com
    MEDHUB_CLIENT_ID        OAuth client id
    MEDHUB_CLIENT_SECRET    OAuth client secret

Examples:

    # Pull trainees data and save to CSV
    python medhub_fetch.py v1/trainees --output-dir data/

    # Fetch evaluations, keep as DataFrame in memory, show summary only
    python medhub_fetch.py v1/evaluations --max-pages 2 --verbose

"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

import pandas as pd
import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


JSONDict = Dict[str, Any]


class MedHubError(RuntimeError):
    """Raised when MedHub responds with an unexpected payload."""


@dataclass
class OAuthToken:
    access_token: str
    token_type: str
    expires_at: float

    @classmethod
    def from_response(cls, payload: Mapping[str, Any]) -> "OAuthToken":
        try:
            access_token = payload["access_token"]
            token_type = payload.get("token_type", "Bearer")
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise MedHubError("OAuth token response missing access_token") from exc

        expires_in = payload.get("expires_in", 3600)
        now = time.time()
        return cls(access_token=access_token, token_type=token_type, expires_at=now + float(expires_in))


class MedHubClient:
    """Minimal MedHub API client with pagination helpers."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        *,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

        self.session: Session = requests.Session()
        self._configure_retries()

        self._token: Optional[OAuthToken] = None
        self._last_response: Optional[Response] = None

    # ------------------------------------------------------------------
    # Session & auth handling
    # ------------------------------------------------------------------
    def _configure_retries(self) -> None:
        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _token_valid(self) -> bool:
        if self._token is None:
            return False
        buffer_seconds = 30
        return (self._token.expires_at - buffer_seconds) > time.time()

    def _authenticate(self, *, force: bool = False) -> OAuthToken:
        if not force and self._token_valid():
            return self._token  # type: ignore[return-value]

        token_url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        self.logger.debug("Requesting new OAuth token from %s", token_url)
        response = self.session.post(token_url, data=payload, timeout=self.timeout, verify=self.verify_ssl)
        self._raise_for_status(response)
        token = OAuthToken.from_response(response.json())

        self.session.headers.update({"Authorization": f"{token.token_type} {token.access_token}"})
        self._token = token
        return token

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self.base_url}{endpoint}"

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
    ) -> JSONDict:
        self._authenticate()
        url = self._build_url(endpoint)

        self.logger.debug("%s %s", method, url)
        response = self.session.request(
            method,
            url,
            params=params,
            json=json_body,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )

        if response.status_code == 401:
            # Refresh token and retry once.
            self.logger.info("Token expired, refreshing and retrying request")
            self._authenticate(force=True)
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

        self._raise_for_status(response)
        self._last_response = response

        if not response.content:
            return {}

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type == "application/json":
            return response.json()

        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise MedHubError(f"Unexpected response format for {endpoint}") from exc

    def _raise_for_status(self, response: Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = self._extract_error_detail(response)
            raise MedHubError(detail) from exc

    @staticmethod
    def _extract_error_detail(response: Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        return f"MedHub API error ({response.status_code}): {payload}"

    # ------------------------------------------------------------------
    # Public fetch helpers
    # ------------------------------------------------------------------
    def iter_records(
        self,
        endpoint: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        per_page: int = 200,
        page_param: str = "page",
        per_page_param: str = "per_page",
        data_key: Optional[str] = "data",
        max_pages: Optional[int] = None,
    ) -> Iterator[JSONDict]:
        """Yield individual records across paginated responses."""

        page = 1
        base_params: Dict[str, Any] = dict(params or {})

        while True:
            query = dict(base_params)
            query[page_param] = page
            if per_page_param:
                query.setdefault(per_page_param, per_page)

            payload = self._request("GET", endpoint, params=query)

            if data_key is None:
                records = payload
            else:
                records = payload.get(data_key, payload)

            if not isinstance(records, list):
                raise MedHubError(
                    "Expected list of records from MedHub response. "
                    f"endpoint={endpoint!r}, data_key={data_key!r}"
                )

            if not records:
                break

            for record in records:
                yield record

            page += 1
            if max_pages and page > max_pages:
                break
            if not self._has_next_page(payload, len(records), per_page):
                break

    def fetch_dataframe(
        self,
        endpoint: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        per_page: int = 200,
        data_key: Optional[str] = "data",
        normalize: bool = True,
        record_path: Optional[str] = None,
        meta: Optional[List[str]] = None,
        max_pages: Optional[int] = None,
    ) -> pd.DataFrame:
        """Return a pandas DataFrame for the requested endpoint."""

        records = list(
            self.iter_records(
                endpoint,
                params=params,
                per_page=per_page,
                data_key=data_key,
                max_pages=max_pages,
            )
        )

        if not records:
            return pd.DataFrame()

        if normalize:
            # If a nested record_path is provided, rely on json_normalize.
            if record_path:
                return pd.json_normalize(records, record_path=record_path, meta=meta)
            return pd.json_normalize(records)

        return pd.DataFrame(records)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _has_next_page(self, payload: Mapping[str, Any], batch_size: int, per_page: int) -> bool:
        headers = (self._last_response.headers if self._last_response is not None else {})

        header_next = headers.get("X-Next-Page") or headers.get("x-next-page")
        if header_next:
            return header_next not in {"", "0", "null", "None"}

        links = payload.get("links")
        if isinstance(links, Mapping) and links.get("next"):
            return True

        meta = payload.get("meta")
        if isinstance(meta, Mapping):
            current_page = meta.get("page") or meta.get("current_page")
            total_pages = meta.get("total_pages") or meta.get("pages")
            if current_page is not None and total_pages is not None:
                try:
                    return int(current_page) < int(total_pages)
                except (TypeError, ValueError):
                    pass

            total_count = meta.get("total") or meta.get("count") or meta.get("record_count")
            if current_page is not None and total_count is not None and per_page:
                try:
                    return int(current_page) * per_page < int(total_count)
                except (TypeError, ValueError):
                    pass

        return batch_size >= per_page


def parse_key_value_pairs(pairs: Iterable[str]) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Parameter must be in key=value format: {item!r}")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def save_dataframe(df: pd.DataFrame, output_path: Path, fmt: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        df.to_csv(output_path, index=False)
    elif fmt == "parquet":
        df.to_parquet(output_path, index=False)
    elif fmt == "json":
        df.to_json(output_path, orient="records", lines=True)
    else:  # pragma: no cover - argparse guards against this
        raise ValueError(f"Unsupported output format: {fmt}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "endpoint",
        nargs="+",
        help="MedHub API endpoint(s) to fetch, e.g. v1/trainees or v1/evaluations",
    )
    parser.add_argument("--base-url", default=os.getenv("MEDHUB_BASE_URL"), help="MedHub API base URL")
    parser.add_argument("--client-id", default=os.getenv("MEDHUB_CLIENT_ID"), help="OAuth client id")
    parser.add_argument("--client-secret", default=os.getenv("MEDHUB_CLIENT_SECRET"), help="OAuth client secret")
    parser.add_argument("--verify-ssl", action="store_true", default=True, help="Verify TLS certificates (default: true)")
    parser.add_argument(
        "--skip-ssl-verify",
        action="store_true",
        help="Disable TLS certificate verification (useful for MedHub sandboxes)",
    )
    parser.add_argument("--per-page", type=int, default=200, help="Number of records per API page")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to fetch (for testing)")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional query parameter(s) applied to all requests",
    )
    parser.add_argument(
        "--data-key",
        default="data",
        help="Response key that contains the record list (set to '' to use the root)",
    )
    parser.add_argument(
        "--record-path",
        default=None,
        help="Optional nested list key inside each record for json_normalize",
    )
    parser.add_argument(
        "--meta",
        action="append",
        default=None,
        help="Metadata fields to include when flattening nested structures",
    )
    parser.add_argument("--no-normalize", action="store_true", help="Skip pandas.json_normalize and keep raw columns")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to save each DataFrame (filename derives from endpoint)",
    )
    parser.add_argument(
        "--output-format",
        choices=("csv", "parquet", "json"),
        default="csv",
        help="File format when saving DataFrames",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Increase logging verbosity")
    return parser


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def validate_cli_args(args: argparse.Namespace) -> None:
    if not args.base_url:
        raise SystemExit("Missing --base-url or MEDHUB_BASE_URL")
    if not args.client_id:
        raise SystemExit("Missing --client-id or MEDHUB_CLIENT_ID")
    if not args.client_secret:
        raise SystemExit("Missing --client-secret or MEDHUB_CLIENT_SECRET")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)

    try:
        params = parse_key_value_pairs(args.param)
    except ValueError as exc:
        parser.error(str(exc))

    if args.skip_ssl_verify:
        args.verify_ssl = False

    validate_cli_args(args)

    logger = logging.getLogger("medhub")

    client = MedHubClient(
        base_url=args.base_url,
        client_id=args.client_id,
        client_secret=args.client_secret,
        verify_ssl=args.verify_ssl,
        timeout=args.timeout,
        logger=logger,
    )

    data_key = args.data_key or None
    meta_fields = args.meta
    record_path = args.record_path
    normalize = not args.no_normalize

    exit_code = 0

    for endpoint in args.endpoint:
        logger.info("Fetching %s", endpoint)
        try:
            df = client.fetch_dataframe(
                endpoint,
                params=params,
                per_page=args.per_page,
                data_key=data_key,
                normalize=normalize,
                record_path=record_path,
                meta=meta_fields,
                max_pages=args.max_pages,
            )
        except MedHubError as exc:
            logger.error("Failed to fetch %s: %s", endpoint, exc)
            exit_code = 1
            continue

        if df.empty:
            logger.warning("%s returned zero rows", endpoint)
        else:
            logger.info("%s returned %d rows x %d columns", endpoint, len(df), len(df.columns))

        if args.output_dir:
            safe_name = endpoint.strip("/").replace("/", "_") or "root"
            filename = f"{safe_name}.{args.output_format}"
            output_path = args.output_dir / filename
            logger.info("Saving %s to %s", endpoint, output_path)
            save_dataframe(df, output_path, args.output_format)
        else:
            # Print a lightweight preview for interactive runs.
            with pd.option_context("display.max_columns", 20, "display.width", 120):
                print(f"\nEndpoint: {endpoint}")
                print(df.head())

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

