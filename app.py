"""California Rent Map — interactive Zillow rental explorer (Orange County snapshot, May 2025).

Run:  streamlit run app.py
"""
import html

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import logic as L

st.set_page_config(page_title="California Rent Map", page_icon="🏙️", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 1.6rem; max-width: 1500px;}
.card {background:#151a23; border:1px solid #232a36; border-radius:14px; padding:14px 16px; margin-bottom:6px;}
.card.sel {border-color:#7C5CFF; box-shadow:0 0 0 1px #7C5CFF;}
.card .loc {color:#8b93a5; font-size:0.78rem;}
.card .nm {font-weight:650; font-size:1.02rem; margin:2px 0 6px 0; color:#f2f4f8;}
.card .pill {display:inline-block; background:#222a38; color:#c9cfdc; border-radius:8px;
             padding:2px 8px; font-size:0.74rem; margin-right:5px;}
.card .px {font-size:1.25rem; font-weight:700; color:#fff; margin-top:8px;}
.card .px small {font-weight:400; color:#8b93a5; font-size:0.78rem;}
.badge {float:right; font-size:0.72rem; padding:2px 8px; border-radius:8px; font-weight:600;}
.badge.High {background:#4a1f2a; color:#ff8fa3;}
.badge.Low {background:#16402f; color:#7ee2b0;}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def get_data() -> pd.DataFrame:
    return L.load()


t = get_data()

# ------------------------------------------------------------------ header
st.title("California Rent Map")
st.caption(
    "Orange County, CA · Zillow rental listings scraped **May 2025** — historical asking rents, "
    "not current prices. Apartment-complex prices are Zillow “starting at” rents (shown with +)."
)

# ------------------------------------------------------------------ sidebar filters
with st.sidebar:
    st.header("Filters")
    cities = st.multiselect("City", sorted(t["city"].unique()), placeholder="All cities")
    zip_pool = t[t["city"].isin(cities)] if cities else t
    zips = st.multiselect("ZIP code", sorted(zip_pool["zip"].unique()), placeholder="All ZIP codes")
    beds = st.multiselect("Bedrooms", L.BED_OPTIONS, default=L.BED_OPTIONS)
    rent_lo, rent_hi = st.slider(
        "Monthly rent ($)", 500, L.RENT_SLIDER_MAX, (500, L.RENT_SLIDER_MAX), step=100,
        help=f"Drag the right handle all the way to ${L.RENT_SLIDER_MAX:,} to include everything above it.",
    )
    if rent_hi >= L.RENT_SLIDER_MAX:
        st.caption(f"Showing ${rent_lo:,} and up")
    seg_options = sorted(t["segment"].unique())
    segments = st.multiselect("Property type", seg_options, default=seg_options)
    st.divider()
    flag_pct = st.slider(
        "“Unusual price” threshold", 15, 100, 35, step=5, format="%d%%",
        help="Flag a listing when its rent is this far above/below the median for the same "
        "city, bedroom count and property type.",
    )
    flag_thr = flag_pct / 100

f = L.apply_filters(t, cities, zips, beds, rent_lo, rent_hi, segments)
if f.empty:
    st.warning("No listings match these filters. Try widening the rent range or bedroom selection.")
    st.stop()

p = L.aggregate_properties(f, flag_thr)
p_map = p[p["has_coords"]].copy()

tab_map, tab_market, tab_unusual, tab_about = st.tabs(
    ["🗺️ Map explorer", "📊 Market comparison", "🚩 Unusual prices", "ℹ️ About the data"]
)

# ================================================================== MAP TAB
with tab_map:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Properties", f"{len(p):,}")
    m2.metric("Unit types / listings", f"{len(f):,}")
    m3.metric("Median rent", L.money(f["rent"].median()))
    m4.metric("Flagged unusual", f"{(p['flag'] != '').sum():,}")

    st.session_state.setdefault("selected_id", None)
    st.session_state.setdefault("last_map_click", None)

    col_list, col_map = st.columns([1, 1.7], gap="medium")

    # ---- map (built first so a click can update the selection before the list renders)
    with col_map:
        lat0, lon0, zoom = L.map_view(p_map)
        lo, hi = p_map["rent_med"].quantile([0.05, 0.95]) if len(p_map) > 1 else (0, 1)
        p_map["hover_loc"] = p_map["street"] + ", " + p_map["city"]
        p_map["hover_rent"] = p_map["rent_label"] + " · " + p_map["beds_label"]
        fig = px.scatter_map(
            p_map,
            lat="lat",
            lon="lon",
            color="rent_med",
            color_continuous_scale="Plasma",
            range_color=(lo, hi),
            custom_data=["property_id", "name", "hover_loc", "hover_rent"],
            center={"lat": lat0, "lon": lon0},
            zoom=zoom,
            height=640,
            map_style="carto-darkmatter",
        )
        fig.update_traces(
            marker={"size": 10, "opacity": 0.9},
            hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[2]}<br>%{customdata[3]}<extra></extra>",
        )
        fig.update_layout(
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            coloraxis_colorbar={
                "title": "Typical rent", "tickprefix": "$", "thickness": 12, "len": 0.5, "y": 0.8,
            },
        )
        event = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key="rent_map")
        st.caption(
            "Each dot is a property, colored by its typical (median) rent among the units that match your "
            "filters; the color scale is clipped to the 5th–95th percentile so outliers don't wash it out. "
            f"{len(p) - len(p_map)} matching properties have no coordinates and appear only in the list."
        )

    clicked = None
    try:
        for pt in event.selection.points:
            cd = pt.get("customdata")
            if cd:
                clicked = cd[0]
                break
    except Exception:
        clicked = None
    if clicked is None:
        st.session_state["last_map_click"] = None
    elif clicked != st.session_state["last_map_click"]:
        st.session_state["last_map_click"] = clicked
        st.session_state["selected_id"] = clicked

    def choose(pid):
        st.session_state["selected_id"] = pid

    # ---- list of cards
    with col_list:
        sort_by = st.selectbox(
            "Sort list by", ["Lowest rent", "Highest rent", "Most unusually priced"], label_visibility="collapsed"
        )
        if sort_by == "Lowest rent":
            ps = p.sort_values("rent_med")
        elif sort_by == "Highest rent":
            ps = p.sort_values("rent_med", ascending=False)
        else:
            ps = p.sort_values("unusualness", ascending=False)

        sel_id = st.session_state["selected_id"]
        with st.container(height=640):
            for r in ps.head(40).itertuples():
                badge = f'<span class="badge {r.flag}">{r.flag} for area</span>' if r.flag else ""
                sel_cls = " sel" if r.property_id == sel_id else ""
                st.markdown(
                    f"""<div class="card{sel_cls}">
<div class="loc">📍 {html.escape(r.city)} · {html.escape(r.segment)} {badge}</div>
<div class="nm">{html.escape(str(r.name))}</div>
<span class="pill">{html.escape(r.beds_label)}</span><span class="pill">{r.n_units} unit type{'s' if r.n_units != 1 else ''}</span>
<div class="px">{html.escape(r.rent_label)} <small>/month</small></div></div>""",
                    unsafe_allow_html=True,
                )
                st.button("View details", key=f"btn_{r.property_id}", on_click=choose, args=(r.property_id,))
            if len(ps) > 40:
                st.caption(f"Showing 40 of {len(ps):,} properties — narrow the filters or click the map to explore more.")

    # ---- detail panel
    st.divider()
    sel_id = st.session_state["selected_id"]
    if sel_id is None:
        st.info("Click a dot on the map or press **View details** on a card to inspect a property.")
    else:
        full = t[t["property_id"] == sel_id].sort_values(["beds", "rent"])
        if full.empty:
            st.session_state["selected_id"] = None
        else:
            head = full.iloc[0]
            visible = sel_id in set(p["property_id"])
            st.subheader(head["property_name"])
            addr = f"{head['street']}, {head['city']}, CA {head['zip']}" if head["street"] != "Address not disclosed" else f"{head['city']}, CA {head['zip']}"
            st.write(f"📍 {addr}  ·  {head['segment']}")
            if not visible:
                st.caption("This property is hidden by your current filters; showing all of its listed unit types.")
            d1, d2, d3, d4 = st.columns([1, 1, 1, 1.2])
            d1.metric("Lowest rent", L.money(full["rent"].min()))
            d2.metric("Highest rent", L.money(full["rent"].max()))
            d3.metric("Unit types", len(full))
            d4.link_button("Open on Zillow ↗", head["zillow_url"])

            tbl = pd.DataFrame(
                {
                    "Bedrooms": full["bed_label"],
                    "Rent": full["rent"],
                    "Price type": np.where(full["rent_is_starting"], "Starting at", "Listed"),
                    "Sq ft": full["sqft"],
                    "Baths": full["baths"],
                    "vs. peers": full["vs_peer"] * 100,
                    "Peer median": full["peer_median"],
                    "Peers =": full["peer_basis"],
                    "Available": full["available"].dt.date,
                    "Days on Zillow": full["days_on_zillow"],
                    "Price change": full["price_note"],
                    "Zillow rent est.": full["rent_zestimate"],
                }
            )
            st.dataframe(
                tbl,
                hide_index=True,
                column_config={
                    "Rent": st.column_config.NumberColumn(format="$%d"),
                    "Peer median": st.column_config.NumberColumn(format="$%d"),
                    "vs. peers": st.column_config.NumberColumn(format="%+.0f%%"),
                    "Zillow rent est.": st.column_config.NumberColumn(format="$%d"),
                    "Sq ft": st.column_config.NumberColumn(format="%d"),
                    "Days on Zillow": st.column_config.NumberColumn(format="%d"),
                },
            )
            st.caption(
                "“vs. peers” compares this rent with the median for the same bedroom count and property type "
                "in the same city (or all of Orange County when a city has fewer than 5 comparable listings)."
            )

# ================================================================== MARKET TAB
with tab_market:
    st.subheader("Median rent by city")
    if len(set(f["bed_bucket"])) > 1:
        st.info(
            "Tip: you're mixing bedroom counts, which skews city comparisons (a city with more 3-bedroom "
            "houses will look pricier). Pick a single bedroom count in the sidebar for a like-for-like view."
        )
    min_n = st.slider("Minimum listings per city", 1, 30, 8)
    cm = L.city_medians(f, min_n)
    if cm.empty:
        st.write("No city has that many listings under the current filters.")
    else:
        county_med = f["rent"].median()
        bar = px.bar(
            cm, x="median_rent", y="city", orientation="h", color="median_rent",
            color_continuous_scale="Plasma", text=cm["median_rent"].map(L.money),
            hover_data={"listings": True, "properties": True, "median_rent": ":$,.0f"},
            height=max(320, 26 * len(cm) + 80),
        )
        bar.add_vline(x=county_med, line_dash="dot", line_color="#9aa3b5",
                      annotation_text=f"All filtered listings: {L.money(county_med)}", annotation_position="top")
        bar.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title="Median monthly rent",
                          margin={"l": 0, "r": 10, "t": 30, "b": 0}, xaxis_tickprefix="$")
        bar.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(bar)

    st.subheader("Rent by apartment size")
    box = px.box(
        f.sort_values("beds"), x="bed_label", y="rent", color="segment", log_y=True, points=False, height=420,
        labels={"bed_label": "Bedrooms", "rent": "Monthly rent (log scale)", "segment": "Type"},
    )
    box.update_layout(margin={"l": 0, "r": 0, "t": 10, "b": 0}, yaxis_tickprefix="$")
    st.plotly_chart(box)
    piv = f.pivot_table(index="bed_label", columns="segment", values="rent", aggfunc="median")
    order = list(dict.fromkeys(L.bed_label(i) for i in sorted(f["beds"].unique())))
    st.dataframe(piv.reindex(order).round(0), column_config={c: st.column_config.NumberColumn(format="$%d") for c in piv.columns})
    st.caption("Median monthly rent by bedroom count and property type, for the listings matching your filters.")

# ================================================================== UNUSUAL TAB
with tab_unusual:
    st.subheader("Listings priced unusually high or low")
    st.write(
        f"Each listing is compared with the median rent of its peers — same bedroom count and property type, "
        f"in the same city (or all of Orange County when fewer than 5 peers exist). "
        f"Flag threshold: **±{flag_pct}%** (change it in the sidebar)."
    )
    cfg = {
        "Rent": st.column_config.NumberColumn(format="$%d"),
        "Peer median": st.column_config.NumberColumn(format="$%d"),
        "vs. peers": st.column_config.NumberColumn(format="%+.0f%%"),
        "Zillow": st.column_config.LinkColumn(display_text="Open ↗"),
    }

    def show(df):
        out = pd.DataFrame(
            {
                "Property": df["property_name"], "City": df["city"], "Type": df["segment"],
                "Bedrooms": df["bed_label"], "Rent": df["rent"], "Peer median": df["peer_median"],
                "vs. peers": df["vs_peer"] * 100, "Peers =": df["peer_basis"], "Zillow": df["zillow_url"],
            }
        )
        st.dataframe(out, hide_index=True, column_config=cfg)

    hi_df = L.unusual(f, flag_thr, True)
    lo_df = L.unusual(f, flag_thr, False)
    st.markdown(f"#### 🔺 Priced high ({(f['vs_peer'] >= flag_thr).sum():,} listings match; top 25 shown)")
    show(hi_df)
    st.markdown(f"#### 🔻 Priced low ({(f['vs_peer'] <= -flag_thr).sum():,} listings match; top 25 shown)")
    show(lo_df)
    st.caption(
        "Heads-up: this only controls for city, bedrooms and type — not square footage, condition, view or "
        "amenities. A 'high' flag is often a luxury or oceanfront home; a 'low' flag can be a small or older "
        "unit, a room-share, or a data quirk. Treat flags as places to look, not verdicts."
    )

# ================================================================== ABOUT TAB
with tab_about:
    st.subheader("About this data")
    st.markdown(
        f"""
- **Coverage:** Orange County, CA only — {t['city'].nunique()} cities and {t['zip'].nunique()} ZIP codes.
  It is not statewide.
- **Snapshot date:** scraped around May 2025. These are historical asking rents.
- **What a row is:** one priced unit type. Apartment complexes list up to four floor-plan
  “starting at” prices; houses, condos and individual apartment listings have a single rent.
- **Cleaning:** manufactured-home “space” rows were dropped (their prices were lot sale prices, e.g. $139,000/mo);
  rows with unknown bedrooms were dropped; {int((~t['has_coords']).sum())} unit rows lack coordinates, so
  they show in lists and charts but not on the map.
- **Undisclosed addresses:** {int((t['property_name'] == 'Undisclosed address').sum())} listings hide their street address;
  they are still mapped by Zillow's approximate coordinates when available.
- **Total in this app:** {len(t):,} unit-type rows across {t['property_id'].nunique():,} properties.
"""
    )
