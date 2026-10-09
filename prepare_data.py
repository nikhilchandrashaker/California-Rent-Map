"""
Turn the raw Zillow scrape (300 columns, 2 listing shapes) into one tidy table.

Usage:
    python prepare_data.py path/to/Zillow_Rent_Data.csv
Writes: data/rentals_clean.csv

Raw data has two shapes of row:
  * Building rows (604): a complex with up to 4 floor-plan prices in units/0..3
  * Unit rows (1,896): one individual listing (apartment, house, condo...)
We explode building rows so every output row is ONE priced unit type, and keep a
property_id (the Zillow page URL) so rows can be grouped back into properties.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = sys.argv[1] if len(sys.argv) > 1 else "Zillow_Rent_Data_xlsx_-_Data.csv"
OUT = Path(__file__).parent / "data" / "rentals_clean.csv"

# Peer groups with fewer listings than this fall back to a county-wide median.
MIN_PEERS = 5


def money(s):
    """'$2,499+' -> 2499.0"""
    return pd.to_numeric(s.astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")


def segment(home_type, is_complex):
    if is_complex:
        return "Apartment"
    return {
        "APARTMENT": "Apartment",
        "SINGLE_FAMILY": "House",
        "MULTI_FAMILY": "House",
        "CONDO": "Condo / Townhome",
        "TOWNHOUSE": "Condo / Townhome",
    }.get(home_type, "Other")


def main():
    df = pd.read_csv(RAW, low_memory=False)
    n_raw = len(df)

    df["lat"] = df["latLong/latitude"].fillna(df["hdpData/homeInfo/latitude"])
    df["lon"] = df["latLong/longitude"].fillna(df["hdpData/homeInfo/longitude"])
    df["city"] = df["addressCity"].str.strip()
    df["zip"] = df["addressZipcode"].astype(str).str.zfill(5)

    is_bldg = df["isBuilding"].notna()

    # ---------- building rows -> one row per floor plan ----------
    frames = []
    for i in range(4):
        b = df[is_bldg & df[f"units/{i}/price"].notna()].copy()
        if b.empty:
            continue
        b["beds"] = b[f"units/{i}/beds"]
        b["rent"] = money(b[f"units/{i}/price"])
        b["rent_is_starting"] = b[f"units/{i}/price"].astype(str).str.contains(r"\+")
        b["property_name"] = b["buildingName"].fillna(b["statusText"])
        b["street"] = b["address"].str.split(",").str[0].str.strip()
        b["home_type"] = "APARTMENT"
        b["kind"] = "complex"
        b["baths"] = np.nan
        b["sqft"] = np.nan
        b["rent_zestimate"] = np.nan
        b["days_on_zillow"] = np.nan
        b["price_note"] = ""
        b["available"] = pd.NaT
        frames.append(b)

    # ---------- individual unit rows ----------
    u = df[~is_bldg & df["price"].notna()].copy()
    u["beds"] = u["beds"]
    u["rent"] = u["unformattedPrice"]
    u["rent_is_starting"] = u["price"].astype(str).str.contains(r"\+")
    parts = u["address"].str.split(", ")
    # "Name, 123 Main St, City, CA 92780" has 4 parts; no-name addresses have 3.
    has_name = parts.str.len() >= 4
    u["property_name"] = np.where(has_name, parts.str[0], None)
    u["street"] = u["addressStreet"].str.replace(r"\s+", " ", regex=True)
    u["home_type"] = u["hdpData/homeInfo/homeType"]
    u["kind"] = np.where(u["detailUrl"].str.contains("/apartments/|/b/"), "complex", "single")
    u["sqft"] = u["area"]
    u["rent_zestimate"] = u["hdpData/homeInfo/rentZestimate"]
    u["days_on_zillow"] = u["hdpData/homeInfo/daysOnZillow"]
    u["price_note"] = u["hdpData/homeInfo/priceReduction"].fillna("")
    u["available"] = pd.to_datetime(u["availabilityDate"], errors="coerce")
    frames.append(u)

    t = pd.concat(frames, ignore_index=True)

    # ---------- cleaning ----------
    # Manufactured-home "SPACE" rows carry lot sale prices ($139,000/mo), not rents.
    t = t[t["home_type"] != "MANUFACTURED"]
    t = t[t["rent"].between(500, 200_000)]
    t["beds"] = t["beds"].fillna(-1).astype(int)  # -1 = unknown
    t["segment"] = [segment(h, k == "complex") for h, k in zip(t["home_type"], t["kind"])]
    t["property_id"] = t["detailUrl"]
    # Single homes with no name: use the street address as the display name.
    t["property_name"] = t["property_name"].fillna(t["street"])
    t["undisclosed_address"] = t["address"].str.contains("undisclosed", case=False, na=False)
    t["has_coords"] = t["lat"].notna() & t["lon"].notna()

    # ---------- peer medians for "unusually high / low" flags ----------
    keys_local = ["city", "beds", "segment"]
    keys_wide = ["beds", "segment"]
    local = t.groupby(keys_local)["rent"].transform("median")
    local_n = t.groupby(keys_local)["rent"].transform("size")
    wide = t.groupby(keys_wide)["rent"].transform("median")
    t["peer_median"] = np.where(local_n >= MIN_PEERS, local, wide)
    t["peer_basis"] = np.where(local_n >= MIN_PEERS, "same city", "all Orange County")
    t["vs_peer"] = t["rent"] / t["peer_median"] - 1  # +0.40 = 40% above peers

    cols = [
        "property_id", "property_name", "kind", "segment", "home_type", "street", "city", "zip",
        "lat", "lon", "has_coords", "undisclosed_address", "beds", "baths", "sqft", "rent",
        "rent_is_starting", "rent_zestimate", "peer_median", "peer_basis", "vs_peer",
        "days_on_zillow", "price_note", "available", "detailUrl",
    ]
    t = t[cols].rename(columns={"detailUrl": "zillow_url"})
    OUT.parent.mkdir(exist_ok=True)
    t.to_csv(OUT, index=False)

    props = t["property_id"].nunique()
    print(f"raw rows: {n_raw}")
    print(f"clean rows (priced unit types): {len(t)}  |  properties: {props}")
    print(f"rows without map coordinates: {(~t['has_coords']).sum()}")
    print(t.groupby("segment")["rent"].agg(["count", "median"]).round(0))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
