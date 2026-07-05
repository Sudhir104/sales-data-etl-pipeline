"""
Extract layer.

Two source types, mirroring the resume project:
  1. A flat-file source (CSV export of raw sales transactions).
  2. A REST API source (product master / catalog data). We try a live public
     API first and transparently fall back to a cached JSON snapshot if the
     network isn't reachable -- this keeps the pipeline runnable offline
     (e.g. in CI or an interview sandbox) while still demonstrating a real
     REST integration.
"""
import json
import logging

import pandas as pd
import requests

logger = logging.getLogger("etl.extract")


def extract_sales_csv(path: str) -> pd.DataFrame:
    """Read the raw sales transactions CSV exactly as it comes from the source system."""
    df = pd.read_csv(path, dtype=str)  # read as str first; typing/casting happens in transform
    logger.info("Extracted %d raw sales rows from %s", len(df), path)
    return df


def extract_products_api(api_url: str, cache_path: str, timeout: int = 5) -> pd.DataFrame:
    """
    Extract the product master from a REST API. Falls back to a local cache
    if the API is unreachable (no internet, rate-limited, timeout, etc.).
    """
    try:
        resp = requests.get(api_url, timeout=timeout)
        resp.raise_for_status()
        raw = resp.json()
        source = "live API"
    except Exception as exc:  # network errors, timeouts, bad status codes, etc.
        logger.warning("Live API extract failed (%s). Falling back to cached snapshot.", exc)
        with open(cache_path, "r") as f:
            raw = json.load(f)
        source = "cached snapshot"

    df = pd.json_normalize(raw)
    logger.info("Extracted %d product records from %s", len(df), source)
    return df
