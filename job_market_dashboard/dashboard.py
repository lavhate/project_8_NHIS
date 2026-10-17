"""Job market dashboard (Task 6).

Run:  streamlit run dashboard.py

Monthly refresh: copy the new Upwork CSV export into the `data/` folder (or the folder in JOBS_DATA_DIR) and
click "Reload data". New files are detected automatically and combined with the old ones; duplicate
postings are removed.
"""
import glob
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import market_metrics as mm

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
CSV_PATTERN = "all_upwork_jobs_*.csv"

st.set_page_config(page_title="Job Market Dashboard", page_icon=":bar_chart:", layout="wide")


# ---------------------------------------------------------------- data
def discover_csvs(extra_folder: str) -> list[str]:
    folders = [DATA_DIR, os.path.join(HERE, "..", "data"), os.path.join(HERE, ".."), extra_folder]
    found = set()
    for folder in folders:
        if folder and os.path.isdir(folder):
            found.update(os.path.abspath(p) for p in glob.glob(os.path.join(folder, CSV_PATTERN)))
    env = os.environ.get("JOBS_CSV")
    if env and os.path.exists(env):
        found.add(os.path.abspath(env))
    env_dir = os.environ.get("JOBS_DATA_DIR")                      # optional shared data folder
    if env_dir and os.path.isdir(env_dir):
        found.update(os.path.abspath(p) for p in glob.glob(os.path.join(env_dir, CSV_PATTERN)))
    return sorted(found)


@st.cache_data(show_spinner="Loading and preparing the data (about 30 seconds, only when files change)...")
def load(signature: tuple):
    """`signature` = ((path, modified time), ...): a new or changed file triggers a reload."""
    jobs = mm.load_jobs([p for p, _ in signature])
    return jobs, jobs.attrs["daily"]


with st.sidebar:
    st.header("Data")
    extra = st.text_input("Extra data folder (optional)", "")
    if st.button("Reload data", help="Clears the cache. New or changed CSV files are also detected automatically."):
        st.cache_data.clear()

paths = discover_csvs(extra)
st.title("Job Market Dashboard")
if not paths:
    st.warning(f"No CSV found. Put the Upwork export (`{CSV_PATTERN}`) in the `data` folder next to this app, "
               "in the project folder, or set the JOBS_CSV environment variable.")
    st.stop()

jobs, daily = load(mm.csv_signature(paths))
all_complete = mm.complete_dates(jobs)

# ---------------------------------------------------------------- sidebar controls
with st.sidebar:
    st.caption(f"{len(paths)} file(s) loaded: " + ", ".join(os.path.basename(p) for p in paths))
    st.header("View")
    granularity = st.radio("Time step", ["Weekly", "Monthly"], horizontal=True)
    freq = "week" if granularity == "Weekly" else "month"
    show_partial = st.checkbox("Show partial periods (grey)", value=True)
    roles = sorted(r for r in jobs["role"].unique() if r != "Other")
    chosen_roles = st.multiselect("Role filter", roles, placeholder="All roles")
    top_countries = jobs["country"].value_counts().index.tolist()
    country = st.selectbox("Client country", ["All countries"] + [c for c in top_countries if c != "Unknown"][:60])

view = jobs
if chosen_roles:
    view = view[view["role"].isin(chosen_roles)]
if country != "All countries":
    view = view[view["country"] == country]
if view.empty:
    st.info("No postings match these filters.")
    st.stop()

pm = mm.period_metrics(view, freq, dates=all_complete)
pm = pm[pm["days_covered"] > 0]
full = pm[pm["is_full_period"]]
unit = "week" if freq == "week" else "month"


def label(ts) -> str:
    return f"{ts:%d %b %Y}" if freq == "week" else f"{ts:%b %Y}"


def trend_chart(col: str, title: str, y_title: str, source: pd.DataFrame = pm) -> go.Figure:
    fig = go.Figure()
    f, p = source[source["is_full_period"]], source[~source["is_full_period"]]
    if f.empty:                                     # e.g. monthly view with only partial months
        fig.add_scatter(x=source.index, y=source[col], mode="lines+markers", name="partial period")
    else:
        fig.add_scatter(x=f.index, y=f[col], mode="lines+markers", name="full period")
        if show_partial and not p.empty:
            fig.add_scatter(x=p.index, y=p[col], mode="markers", name="partial period",
                            marker=dict(color="lightgray", size=10, line=dict(color="gray", width=1)))
    fig.update_layout(title=title, yaxis_title=y_title, height=310, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.2))
    return fig


# ---------------------------------------------------------------- KPIs
st.subheader(f"Latest full {unit} vs the previous one")
if len(full) < 2:
    st.info(f"Fewer than two full {unit}s are available, so no comparison is shown. "
            "Charts below mark incomplete periods in grey.")
else:
    last, prev = full.iloc[-1], full.iloc[-2]
    kpis = [("Postings per day", "postings_per_day", "{:,.0f}"), ("Hourly share", "hourly_share_pct", "{:.1f}%"),
            ("Mean hourly rate", "mean_hourly_rate", "${:,.2f}"), ("Mean fixed budget", "mean_fixed_budget", "${:,.0f}"),
            ("Remote mentions / 10k", "remote_per10k", "{:.1f}"), ("AI / ML share", "ai_ml_share_pct", "{:.2f}%")]
    cols = st.columns(len(kpis))
    for c, (name, key, fmt) in zip(cols, kpis):
        delta = (last[key] / prev[key] - 1) * 100 if prev[key] else None
        c.metric(name, fmt.format(last[key]), None if delta is None else f"{delta:+.1f}%")
    st.caption(f"{unit.capitalize()} starting {label(full.index[-1])} compared with {label(full.index[-2])}. "
               "Small changes (a few percent) are often just noise; see the Data notes tab.")

tab_over, tab_roles, tab_geo, tab_sig, tab_notes = st.tabs(
    ["Overview", "Roles", "Geography", "Work signals", "Data notes"])

with tab_over:
    c1, c2 = st.columns(2)
    c1.plotly_chart(trend_chart("postings_per_day", "Postings per day", "postings / day"), width="stretch")
    c2.plotly_chart(trend_chart("hourly_share_pct", "Share of hourly postings", "%"), width="stretch")
    c3, c4 = st.columns(2)
    c3.plotly_chart(trend_chart("mean_hourly_rate", "Mean hourly rate (midpoint of range)", "$ / hour"), width="stretch")
    c4.plotly_chart(trend_chart("mean_fixed_budget", "Mean fixed-price budget", "$"), width="stretch")
    st.dataframe(pm[["days_covered", "expected_days", "postings", "postings_per_day", "hourly_share_pct",
                     "mean_hourly_rate", "mean_fixed_budget", "is_full_period"]].round(2).rename(index=label),
                 width="stretch")

with tab_roles:
    shares = mm.role_share(view, freq, dates=all_complete, total_df=jobs)
    shares = shares[[c for c in shares.columns if c in pm.index]]
    keep = [c for c in shares.columns if c in full.index] or list(shares.columns)
    top_n = st.slider("Roles shown", 3, 12, 6)
    top_roles = shares[keep].mean(axis=1).nlargest(top_n).index
    fig = go.Figure()
    for r in top_roles:
        fig.add_scatter(x=shares.columns, y=shares.loc[r], mode="lines+markers", name=r)
    fig.update_layout(title="Share of all postings by role (%)", height=420, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")
    if len(keep) >= 2:
        change = pd.DataFrame({"latest %": shares[keep[-1]], "earlier average %": shares[keep[:-1]].mean(axis=1)})
        change["change (percentage points)"] = change["latest %"] - change["earlier average %"]
        st.write(f"**Biggest role movers**: latest full {unit} vs the average of earlier full {unit}s")
        st.dataframe(change.sort_values("change (percentage points)", ascending=False).round(2), width="stretch")

with tab_geo:
    cs = mm.country_share(view, freq, dates=all_complete)
    cs = cs[[c for c in cs.columns if c in pm.index]]
    keep = [c for c in cs.columns if c in full.index] or list(cs.columns)
    fig = go.Figure()
    for c in cs[keep].mean(axis=1).nlargest(8).index:
        fig.add_scatter(x=cs.columns, y=cs.loc[c], mode="lines+markers", name=c)
    fig.update_layout(title="Share of postings by client country (%)", height=420, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")
    g1, g2 = st.columns(2)
    g1.plotly_chart(trend_chart("countries", "Countries with postings", "countries"), width="stretch")
    g2.plotly_chart(trend_chart("us_share_pct", "United States share of postings", "%"), width="stretch")

with tab_sig:
    st.write("Share of posting titles that mention each work-arrangement word (per 10,000 postings). "
             "The data has no remote / on-site field, so this is a keyword proxy.")
    sig = mm.signal_trends(view, freq, dates=all_complete)
    sig = sig.loc[[i for i in sig.index if i in pm.index]]
    choice = st.multiselect("Signals", list(sig.columns), default=["remote", "long term / ongoing", "full time"])
    fig = go.Figure()
    for name in choice:
        fig.add_scatter(x=sig.index, y=sig[name], mode="lines+markers", name=name)
    fig.update_layout(title="Mentions per 10,000 postings", height=400, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("Filtered views contain fewer postings, so these lines get noisier.")

with tab_notes:
    st.markdown(f"""
**Coverage:** {daily.index.min():%d %b %Y} to {daily.index.max():%d %b %Y}; **{int(daily['complete'].sum())} complete days** used.

**Rules used**
- A day counts only if it has at least half the postings typical for that weekday. Partial days (collection gaps and the
  first/last day of an export) are excluded.
- Weeks run **Sunday to Saturday**. A week or month is **full** only if every day in it is complete. Partial periods are shown in grey.
- Rates are the midpoint of the posted hourly range (currency is not stated in the data). The top 1% of rates and budgets is removed as outliers.
- With only a few full periods, changes of a few percent are usually noise. Treat the dashboard as monitoring, not proof of a trend.
""")
    excluded = daily[daily["active"] & ~daily["complete"]]
    if not excluded.empty:
        st.write("Days excluded as partial:")
        st.dataframe(excluded[["n", "typical"]].rename(columns={"n": "postings", "typical": "typical for weekday"})
                     .rename(index=lambda d: f"{d:%a %d %b %Y}"), width="stretch")
    st.write("Period coverage")
    st.dataframe(pm[["days_covered", "expected_days", "is_full_period"]].rename(index=label), width="stretch")
