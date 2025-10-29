import pandas as pd
import numpy as np
from typing import Tuple, List, Optional, Any


def read_listings(csv_paths: List[str]) -> pd.DataFrame:
    frames = []
    for path in csv_paths:
        try:
            df = pd.read_csv(path)
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=[
            "city", "locality", "property_type", "bhk", "area_sqft",
            "total_price", "listed_date", "source",
        ])
    df = pd.concat(frames, ignore_index=True)
    return df


def clean_listings(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    # Standardize columns
    expected = {
        "city": str,
        "locality": str,
        "property_type": str,
        "bhk": "Int64",
        "area_sqft": "float",
        "total_price": "float",
        "listed_date": str,
        "source": str,
    }
    for col, _ in expected.items():
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")

    # Coerce types
    df["bhk"] = pd.to_numeric(df["bhk"], errors="coerce").astype("Int64")
    df["area_sqft"] = pd.to_numeric(df["area_sqft"], errors="coerce")
    df["total_price"] = pd.to_numeric(df["total_price"], errors="coerce")

    # Drop invalid rows
    df = df.dropna(subset=["area_sqft", "total_price"])\
           .query("area_sqft > 0 and total_price > 0")

    # Derive ppsf
    df["ppsf"] = df["total_price"] / df["area_sqft"]

    # Parse date and month
    df["listed_date"] = pd.to_datetime(df["listed_date"], errors="coerce")
    df = df.dropna(subset=["listed_date"]).copy()
    df["listed_month"] = df["listed_date"].dt.to_period("M").astype(str)

    # Basic dedup key
    dedup_key = (
        df["city"].astype(str).str.lower().str.strip()
        + "|" + df["locality"].astype(str).str.lower().str.strip()
        + "|" + df["property_type"].astype(str).str.lower().str.strip()
        + "|" + df["bhk"].astype(str)
        + "|" + (df["area_sqft"].round(0)).astype(int).astype(str)
        + "|" + (df["total_price"].round(-4)).astype(int).astype(str)
    )
    df["_dedup_key"] = dedup_key
    df = df.drop_duplicates(subset=["_dedup_key"]).drop(columns=["_dedup_key"])\
           .reset_index(drop=True)

    # Outlier removal by locality using IQR on ppsf
    def iqr_filter(g: pd.DataFrame) -> pd.DataFrame:
        if g["ppsf"].size < 10:
            return g
        q1 = g["ppsf"].quantile(0.25)
        q3 = g["ppsf"].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return g[(g["ppsf"] >= lower) & (g["ppsf"] <= upper)]

    df = df.groupby(["city", "locality"], group_keys=False).apply(iqr_filter)
    return df.reset_index(drop=True)


def aggregate_by_locality(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "city", "locality", "median_ppsf", "p25_ppsf", "p75_ppsf", "listing_count"
        ])
    agg = (
        df.groupby(["city", "locality"], as_index=False)
          .agg(
              median_ppsf=("ppsf", "median"),
              p25_ppsf=("ppsf", lambda s: s.quantile(0.25)),
              p75_ppsf=("ppsf", lambda s: s.quantile(0.75)),
              listing_count=("ppsf", "size"),
          )
    )
    return agg


def monthly_trend(df: pd.DataFrame, dims: Tuple[str, ...] = ("city", "locality")) -> pd.DataFrame:
    if df.empty:
        cols = list(dims) + [
            "listed_month", "median_ppsf", "p25_ppsf", "p75_ppsf", "listing_count"
        ]
        return pd.DataFrame(columns=cols)
    group_cols = list(dims) + ["listed_month"]
    trend = (
        df.groupby(group_cols, as_index=False)
          .agg(
              median_ppsf=("ppsf", "median"),
              p25_ppsf=("ppsf", lambda s: s.quantile(0.25)),
              p75_ppsf=("ppsf", lambda s: s.quantile(0.75)),
              listing_count=("ppsf", "size"),
          )
    )
    return trend


# --- DB helpers (agnostic: works with psycopg2 connection via pandas) ---

def fetch_all_listings(conn: Any) -> pd.DataFrame:
    """Read all listings by joining tables (SQLite compatible)."""
    sql = (
        "SELECT l.id, c.name AS city, loc.name AS locality, l.property_type, l.bhk, "
        "l.area_sqft, l.total_price, (l.total_price / l.area_sqft) AS ppsf, "
        "l.listed_date AS listed_date, strftime('%Y-%m', l.listed_date) AS listed_month, l.source "
        "FROM listing AS l "
        "INNER JOIN city AS c ON c.id = l.city_id "
        "INNER JOIN locality AS loc ON loc.id = l.locality_id"
    )
    return pd.read_sql_query(sql, conn)


def is_listing_table_empty(conn: Any) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM listing")
    return (cur.fetchone() or (0,))[0] == 0



