# California Rent Map

Two ways to explore the same Zillow rental snapshot (scraped May 2025):

| Version | What it is | Needs |
|---|---|---|
| **Streamlit app** (`app.py`) | Python dashboard with a real street-level basemap | Python + internet for map tiles |
| **Standalone web page** (`web/california_rent_map.html`) | One HTML file, data built in, California outline map, search | Just a browser |

**Coverage: Orange County, CA only** (45 cities, 85 ZIP codes). That is what the spreadsheet contains.
All prices are historical asking rents from May 2025, not current rents.

---

## 1. Streamlit app

```bash
pip install -r requirements.txt
streamlit run app.py
```

The cleaned data (`data/rentals_clean.csv`) is included, so it runs as-is.
Basemap tiles load from the internet, so you need to be online.

**Features**
- Map with one dot per property, colored by typical rent; click a dot to open details
- Filters: city, ZIP, bedrooms, rent range, property type
- Market comparison: median rent by city, rent by bedroom count and type
- Unusual prices: listings far above or below comparable ones (adjustable threshold)
- Property detail cards: unit types, rents, comparison with peers, Zillow link

## 2. Standalone web page

Open `web/california_rent_map.html` in any browser (double-click it). No install, no server.

**Features**
- Simplified California coastline and border (no street tiles), with a **CA** button for the whole state and **Fit** to zoom to your results
- Search box for properties, addresses, cities and ZIP codes
- Same filters, comparison charts and unusual-price tables as the Streamlit app
- Each property links to its Zillow listing, a Google search, and Google Maps

Notes:
- Fonts load from Google Fonts; offline, the page falls back to system fonts.
- The data is embedded in the file (about 660 KB). To change it, rebuild the file from a new dataset; the page does not read `data/rentals_clean.csv`.
- To share it publicly, host the file on any static host (GitHub Pages, Netlify, etc.).

---

## Rebuild the data from the raw Zillow file

```bash
python prepare_data.py path/to/Zillow_Rent_Data_xlsx_-_Data.csv
```

This rewrites `data/rentals_clean.csv`. It affects the Streamlit app only.

## Files

```
app.py                  Streamlit interface (map, filters, cards, charts)
logic.py                Filtering and aggregation (no Streamlit; easy to test)
prepare_data.py         Raw 300-column scrape -> tidy table
data/rentals_clean.csv  3,102 priced unit types across 2,494 properties
requirements.txt        streamlit, plotly, pandas, numpy
.streamlit/config.toml  Dark theme for the Streamlit app
web/california_rent_map.html   Standalone web version
```

## How the data was cleaned

- The raw file mixes two row types: 604 apartment complexes (up to 4 floor plans each) and 1,896 individual listings. Each priced unit type becomes one row.
- Dropped: 4 manufactured-home "space" rows (prices were lot sale prices, e.g. $139,000/mo) and 2 rows with unknown bedrooms.
- 88 raw rows have no coordinates, so they appear in lists and charts but not on the map.
- Complex prices are Zillow "starting at" rents, shown with a +.

## How "unusual price" works

Each listing is compared with the median rent of listings with the same bedroom count and
property type in the same city (or all of Orange County when a city has fewer than 5 such
listings). A listing is flagged when it is more than the chosen threshold (default 35%)
above or below that median. It does not account for size, condition, views or amenities,
so treat flags as places to look, not verdicts.
