# California Rent Map

Interactive Streamlit + Plotly explorer for a Zillow rental snapshot (May 2025).
**Coverage: Orange County, CA only** (45 cities, 85 ZIP codes) — that's what the spreadsheet contains.

## Run it
```bash
pip install -r requirements.txt
streamlit run app.py
```
The cleaned data (`data/rentals_clean.csv`) is included, so the app runs as-is.
Basemap tiles load from the internet, so you need to be online.

## Rebuild the data from the raw file
```bash
python prepare_data.py path/to/Zillow_Rent_Data_xlsx_-_Data.csv
```

## Files
- `app.py` – the Streamlit interface (map, filters, cards, charts)
- `logic.py` – filtering/aggregation (no Streamlit, easy to test)
- `prepare_data.py` – raw 300-column scrape -> tidy table
- `data/rentals_clean.csv` – 3,102 priced unit types across 2,494 properties

## Notes
- Complex prices are Zillow "starting at" rents (shown with +).
- "Unusual price" flags compare against the median for the same city + bedrooms + property type
  (all-county median when a city has < 5 peers). They don't account for size, condition or amenities.
