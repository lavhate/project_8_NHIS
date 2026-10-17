"""Streamlit web app for the job recommender.

Run:  streamlit run streamlit_app.py
Optional: set the JOBS_CSV environment variable to the path of the Upwork CSV.
"""
import os
import re

import pandas as pd
import streamlit as st

from recommender import JobRecommender

CSV_NAME = "all_upwork_jobs_2024-02-07-2024-03-24.csv"
HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = ["react node js developer", "video editor youtube shorts",
            "virtual assistant customer support", "logo design branding"]

st.set_page_config(page_title="Job Recommender", page_icon=":mag:", layout="wide")


# ---------------------------------------------------------------- helpers
def find_csv() -> str | None:
    for path in (os.environ.get("JOBS_CSV"), os.path.join(HERE, "..", CSV_NAME), os.path.join(HERE, "..", "data", CSV_NAME), os.path.join(HERE, CSV_NAME)):
        if path and os.path.exists(path):
            return path
    return None


@st.cache_resource(show_spinner="Building the search index (about 10 seconds, only once)...")
def load_recommender(csv_path: str) -> JobRecommender:
    return JobRecommender(csv_path, verbose=False)


def esc(text) -> str:
    """Escape characters that Streamlit's markdown would interpret (including $ for LaTeX)."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|~$<>])", r"\\\1", str(text))


def money(v):
    if v is None:
        return None
    return f"${v:,.0f}" if float(v).is_integer() else f"${v:,.2f}"


def pay_text(r: dict) -> str:
    if r["job_type"] == "hourly":
        lo, hi = money(r["hourly_low"]), money(r["hourly_high"])
        if lo and hi:
            return f"{lo}/h" if lo == hi else f"{lo} - {hi}/h"
        return f"{lo or hi}/h" if (lo or hi) else "Rate not listed"
    return f"{money(r['budget'])} fixed" if r["budget"] is not None else "Budget not listed"


def set_query(text: str) -> None:
    st.session_state["query"] = text
    st.session_state["searched"] = True


# ---------------------------------------------------------------- load data
csv_path = find_csv()
if csv_path is None:
    st.title("Job Recommender")
    st.warning(f"Could not find `{CSV_NAME}`. Put it in the project folder (next to `recommender_app`), "
               "or type its full path below.")
    typed = st.text_input("Path to the CSV file")
    if typed and os.path.exists(typed):
        csv_path = typed
    elif typed:
        st.error("That file does not exist.")
    if csv_path is None:
        st.stop()

rec = load_recommender(csv_path)
meta = rec.meta()

# ---------------------------------------------------------------- sidebar filters
with st.sidebar:
    st.header("Filters")
    job_type = st.radio("Job type", ["any", "hourly", "fixed"], format_func=str.capitalize, horizontal=True)
    min_hourly = st.number_input("Min hourly rate ($/h)", min_value=0.0, value=0.0, step=5.0,
                                 help="Applies to hourly postings. Postings with no listed rate are excluded when this is above 0.")
    max_hourly = st.number_input("Max hourly rate ($/h, 0 = no limit)", min_value=0.0, value=0.0, step=5.0)
    min_budget = st.number_input("Min fixed budget ($)", min_value=0.0, value=0.0, step=50.0,
                                 help="Applies to fixed-price postings. Postings with no budget are excluded when this is above 0.")
    countries = st.multiselect("Client country", [c["name"] for c in meta["countries"] if c["name"] != "Unknown"][:80],
                               placeholder="Any country")
    window = st.selectbox("Posted within", ["Any time", "Last 3 days", "Last 7 days", "Last 14 days"])
    exclude_raw = st.text_input("Exclude words (comma separated)", placeholder="e.g. data entry, adult")
    top_n = st.slider("Number of results", 5, 50, 10, step=5)
    st.caption(f"Data: {meta['postings']:,} postings, {meta['date_range'][0][:10]} to {meta['date_range'][1][:10]}. "
               "'Posted within' counts back from the newest posting in the data, not from today.")

# ---------------------------------------------------------------- main page
st.title("Job Recommender")
st.write("Describe your skills or the kind of work you want. Results come from recent Upwork postings.")

st.text_area("Your skills / what you are looking for", key="query", height=90,
             placeholder="e.g. react developer, shopify store setup, video editor for youtube")
cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    col.button(ex, key=f"ex_{ex}", on_click=set_query, args=(ex,), width="stretch")

if st.button("Recommend jobs", type="primary", key="search"):
    st.session_state["searched"] = True

query = st.session_state.get("query", "").strip()
if not st.session_state.get("searched"):
    st.stop()
if not query:
    st.warning("Please type your skills or a job keyword.")
    st.stop()

days = {"Any time": None, "Last 3 days": 3, "Last 7 days": 7, "Last 14 days": 14}[window]
try:
    results = rec.recommend(
        query, top_n=top_n, job_type=job_type,
        min_hourly=min_hourly or None, max_hourly=max_hourly or None, min_budget=min_budget or None,
        countries=countries or None, posted_within_days=days,
        exclude_terms=[t.strip() for t in exclude_raw.split(",") if t.strip()],
    )
except ValueError as e:
    st.error(str(e))
    st.stop()

if not results:
    st.info("No postings matched. Try other words (full words work best, for example 'developer' not 'dev') "
            "or relax the filters.")
    st.stop()

st.subheader(f"{len(results)} recommendation{'s' if len(results) != 1 else ''}")
tab_cards, tab_table = st.tabs(["Cards", "Table"])

with tab_cards:
    for r in results:
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"**{esc(r['title'])}**")
            bits = [r["role"], "Hourly" if r["job_type"] == "hourly" else "Fixed price", pay_text(r),
                    r["country"], "Posted " + r["posted_at"][:10]]
            if r["similar_postings"] > 1:
                bits.append(f"{r['similar_postings']} similar postings")
            left.caption(esc("  |  ".join(bits)))
            if r["matched_terms"]:
                left.caption("Matched: " + esc(", ".join(r["matched_terms"])))
            right.metric("Match", f"{r['score']:.0%}")
            right.link_button("View posting", r["link"], width="stretch")

with tab_table:
    table = pd.DataFrame(results)
    table["pay"] = [pay_text(r) for r in results]
    table = table[["title", "role", "job_type", "pay", "country", "posted_at", "score", "similar_postings", "link"]]
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={"link": st.column_config.LinkColumn("Posting", display_text="open"),
                                "score": st.column_config.ProgressColumn("Match", min_value=0.0, max_value=1.0, format="%.2f")})
    st.download_button("Download results as CSV", table.to_csv(index=False).encode("utf-8"),
                       file_name="recommendations.csv", mime="text/csv")

st.caption("Based on posting titles only (no descriptions). Rates are as listed on the posting; the currency is not stated in the data.")
