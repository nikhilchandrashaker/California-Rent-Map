"""Data loading, filtering and aggregation. No Streamlit imports so it is easy to test."""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).parent / "data" / "rentals_clean.csv"
BED_OPTIONS = ["Studio", "1", "2", "3", "4", "5+"]
RENT_SLIDER_MAX = 15_000  # slider top = "no upper limit"


def bed_label(n: int) -> str:
    return "Studio" if n == 0 else (f"{n} bd" if n < 5 else "5+ bd")


def bed_bucket(n: int) -> str:
    return "Studio" if n == 0 else (str(n) if n < 5 else "5+")


def money(x: float) -> str:
    return f"${x:,.0f}"


def load(path: Path = DATA_PATH) -> pd.DataFrame:
    t = pd.read_csv(path, parse_dates=["available"])
    t = t[t["beds"] >= 0].copy()  # drop the handful of rows with unknown bedrooms
    undisclosed = t["property_name"].str.contains("undisclosed", case=False, na=False)
    t.loc[undisclosed, "property_name"] = "Undisclosed address"
    t.loc[undisclosed, "street"] = "Address not disclosed"
    t["bed_bucket"] = t["beds"].map(bed_bucket)
    t["bed_label"] = t["beds"].map(bed_label)
    return t.reset_index(drop=True)


def apply_filters(t, cities, zips, beds, rent_lo, rent_hi, segments) -> pd.DataFrame:
    m = t["bed_bucket"].isin(beds) & t["segment"].isin(segments) & (t["rent"] >= rent_lo)
    if rent_hi < RENT_SLIDER_MAX:
        m &= t["rent"] <= rent_hi
    if cities:
        m &= t["city"].isin(cities)
    if zips:
        m &= t["zip"].isin(zips)
    return t[m]


def _bed_range(lo: int, hi: int) -> str:
    if lo == hi:
        return bed_label(lo)
    first = "Studio" if lo == 0 else str(lo)
    return f"{first}–{bed_label(hi)}"


def _rent_label(lo: float, hi: float, starting: bool) -> str:
    s = money(lo) if lo == hi else f"{money(lo)}–{money(hi)}"
    return s + ("+" if starting else "")


def aggregate_properties(f: pd.DataFrame, flag_threshold: float) -> pd.DataFrame:
    """Collapse matching unit rows to one row per property (= one dot on the map)."""
    if f.empty:
        return pd.DataFrame()
    p = (
        f.groupby("property_id", sort=False)
        .agg(
            name=("property_name", "first"),
            street=("street", "first"),
            city=("city", "first"),
            zip=("zip", "first"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            segment=("segment", "first"),
            has_coords=("has_coords", "first"),
            n_units=("rent", "size"),
            rent_med=("rent", "median"),
            rent_min=("rent", "min"),
            rent_max=("rent", "max"),
            beds_min=("beds", "min"),
            beds_max=("beds", "max"),
            starting=("rent_is_starting", "any"),
            max_vs=("vs_peer", "max"),
            min_vs=("vs_peer", "min"),
            url=("zillow_url", "first"),
        )
        .reset_index()
    )
    p["rent_label"] = [_rent_label(a, b, s) for a, b, s in zip(p.rent_min, p.rent_max, p.starting)]
    p["beds_label"] = [_bed_range(int(a), int(b)) for a, b in zip(p.beds_min, p.beds_max)]
    p["flag"] = np.select(
        [p["max_vs"] >= flag_threshold, p["min_vs"] <= -flag_threshold],
        ["High", "Low"],
        default="",
    )
    p["unusualness"] = np.maximum(p["max_vs"].abs(), p["min_vs"].abs())
    return p


def map_view(p: pd.DataFrame) -> tuple[float, float, float]:
    """Return (center_lat, center_lon, zoom) that frames the plotted points."""
    if p.empty:
        return 33.74, -117.88, 9.5
    lat_span = p.lat.max() - p.lat.min()
    lon_span = (p.lon.max() - p.lon.min()) * np.cos(np.radians(p.lat.mean()))
    span = max(lat_span, lon_span, 0.01)
    zoom = float(np.clip(np.log2(984 / (span * 1.6)) - 0.3, 8.5, 15))
    return float(p.lat.mean()), float(p.lon.mean()), zoom


def city_medians(f: pd.DataFrame, min_listings: int) -> pd.DataFrame:
    c = f.groupby("city").agg(
        median_rent=("rent", "median"), listings=("rent", "size"), properties=("property_id", "nunique")
    )
    return c[c.listings >= min_listings].sort_values("median_rent").reset_index()


def unusual(f: pd.DataFrame, threshold: float, high: bool, n: int = 25) -> pd.DataFrame:
    m = f["vs_peer"] >= threshold if high else f["vs_peer"] <= -threshold
    return f[m].sort_values("vs_peer", ascending=not high).head(n)
