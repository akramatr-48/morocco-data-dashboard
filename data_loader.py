"""Fetch and validate real World Bank observations. Never invent missing data."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from indicators import BY_CODE, COUNTRY, START_YEAR

API_BASE = "https://api.worldbank.org/v2"


class DataUnavailable(RuntimeError):
    """A source could not be fetched or did not contain usable data."""


@dataclass
class IndicatorData:
    frame: pd.DataFrame
    source_updated: str
    retrieved_utc: str


def parse_payload(payload: object, code: str, end_year: int) -> IndicatorData:
    """Validate a single-page WDI response; keep nulls and chronological gaps."""
    if code not in BY_CODE:
        raise ValueError("Unsupported indicator")
    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not isinstance(payload[0], dict)
        or not isinstance(payload[1], list)
    ):
        raise DataUnavailable("The World Bank returned an unexpected response.")

    metadata, observations = payload
    try:
        pages = int(metadata.get("pages", 1))
    except (TypeError, ValueError) as exc:
        raise DataUnavailable("Invalid pagination metadata.") from exc
    if pages != 1:
        raise DataUnavailable("The source returned an incomplete page of data.")

    values = {}
    for item in observations:
        if not isinstance(item, dict):
            raise DataUnavailable("Invalid observation in source data.")
        if item.get("countryiso3code") != COUNTRY:
            raise DataUnavailable("The source returned a different country.")
        indicator = item.get("indicator")
        if not isinstance(indicator, dict) or indicator.get("id") != code:
            raise DataUnavailable("The source returned a different indicator.")
        try:
            year = int(item["date"])
        except (KeyError, ValueError, TypeError) as exc:
            raise DataUnavailable("Invalid year in source data.") from exc
        if not START_YEAR <= year <= end_year:
            continue
        if year in values:
            raise DataUnavailable("Duplicate year in source data.")
        value = item.get("value")
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DataUnavailable("Invalid numeric observation.")
            if not isfinite(value):
                raise DataUnavailable("Non-finite numeric observation.")
        values[year] = value

    if not values or all(value is None for value in values.values()):
        raise DataUnavailable("No observations are available for this indicator.")
    # Reindex to preserve gaps in both the chart and exported CSV.
    frame = pd.DataFrame(
        {"Year": range(START_YEAR, end_year + 1)}
    )
    frame["Value"] = frame["Year"].map(values).astype(float)
    return IndicatorData(
        frame=frame,
        source_updated=str(metadata.get("lastupdated") or "Not supplied"),
        retrieved_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def fetch_indicator(code: str, end_year: int) -> IndicatorData:
    """Fetch one series over HTTPS with bounded timeouts and transient retries."""
    if code not in BY_CODE:
        raise ValueError("Unsupported indicator")
    retry = Retry(
        total=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=False,
    )
    try:
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=retry))
            response = session.get(
                f"{API_BASE}/country/{COUNTRY}/indicator/{code}",
                params={
                    "format": "json",
                    "source": 2,
                    "date": f"{START_YEAR}:{end_year}",
                    "per_page": 1000,
                },
                timeout=(5, 15),
            )
            response.raise_for_status()
            payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DataUnavailable("Could not retrieve this series from the World Bank.") from exc
    return parse_payload(payload, code, end_year)
