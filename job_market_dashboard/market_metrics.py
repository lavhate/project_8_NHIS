"""Shared data preparation and market metrics for the dashboard (Task 6) and the notebook (Tasks 6-8).

Key ideas
---------
* Several monthly CSV exports can be combined: duplicates are removed.
* A day is "complete" if it has at least half the postings usual for that weekday. Partial days
  (collection gaps, first/last day of an export) are excluded from every metric.
* Weeks run Sunday-Saturday ("W-SAT") so the data contains as many full weeks as possible.
* A period is "full" only if all its days are complete; other periods are flagged as partial.
"""
from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd

from roles import assign_role

WEEK_ANCHOR = "W-SAT"
MIN_DAY_RATIO = 0.5

_SPANISH = set("para de la el los las y en un una con por nuestro trabajo que se del al es".split())
REMOTE_PATTERN = re.compile(r"\bremote(?:ly)?\b|work from home|\bwfh\b|home[- ]based|telecommut")
SIGNAL_PATTERNS = {                      # "work arrangement" signals found in titles
    "remote": REMOTE_PATTERN,
    "work from home": re.compile(r"work from home|\bwfh\b|home[- ]based|telecommut"),
    "long term / ongoing": re.compile(r"long[- ]?term|\bongoing\b"),
    "full time": re.compile(r"full[- ]?time"),
    "part time": re.compile(r"part[- ]?time"),
    "contract": re.compile(r"\bcontract(?:or)?\b"),
    "urgent / asap": re.compile(r"\burgent|\basap\b"),
    "on-site / hybrid": re.compile(r"hybrid|on[- ]?site|in[- ]person"),
    "location restricted": re.compile(r"\bus[- ]based|usa only|us only|\bpst\b|\best\b|\bcst\b|time ?zone"),
}


def clean_title(text: str) -> str:
    t = str(text).lower()
    t = re.sub(r"\bsr\.?\b", "senior", t)
    t = re.sub(r"\bjr\.?\b", "junior", t)
    t = re.sub(r"\bva\b", "virtual assistant", t)
    t = re.sub(r"[^a-z0-9+#\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def csv_signature(paths) -> tuple:
    """(path, modified-time) pairs: changes when a file is added or replaced (used as a cache key)."""
    return tuple((p, os.path.getmtime(p)) for p in paths)


def find_csvs(folder: str | None = None, extra: str | None = None) -> list[str]:
    paths = []
    if extra and os.path.exists(extra):
        paths.append(extra)
    for pattern in ([os.path.join(folder, "*.csv")] if folder else []):
        paths += glob.glob(pattern)
    return sorted(set(paths))


def load_jobs(paths: list[str]) -> pd.DataFrame:
    """Read one or more CSV exports, clean them and return one row per posting."""
    raw = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    df = raw.dropna(subset=["title", "published_date"]).copy()
    df["published_date"] = pd.to_datetime(df["published_date"], utc=True, errors="coerce")
    df = df.dropna(subset=["published_date"])
    df["published_date"] = df["published_date"].dt.tz_localize(None)
    df = df.drop_duplicates(subset=["title", "published_date"])

    df["title_clean"] = df["title"].map(clean_title)
    spanish = df["title_clean"].map(lambda s: sum(w in _SPANISH for w in s.split()) >= 2)
    non_latin = df["title"].map(lambda s: any(ord(ch) > 591 for ch in s))
    df = df[~(spanish | non_latin) & (df["title_clean"].str.len() > 2)].copy()

    df["is_hourly"] = df["is_hourly"].astype(bool)
    df["country"] = df["country"].fillna("Unknown")
    df["hourly_mid"] = df[["hourly_low", "hourly_high"]].mean(axis=1)
    df["fixed_budget"] = df["budget"].where(~df["is_hourly"])
    for col in ("hourly_mid", "fixed_budget"):          # remove the top 1% (e.g. 1,000,000 budgets)
        df.loc[df[col] > df[col].quantile(0.99), col] = np.nan

    df["date"] = df["published_date"].dt.normalize()
    df["role"] = df["title_clean"].map(assign_role)
    df["is_remote"] = df["title_clean"].map(lambda s: bool(REMOTE_PATTERN.search(s)))

    # Mark complete days. "Active" days are those with a meaningful number of postings (this
    # ignores the few stray rows that precede the real collection period). A day is complete if it has
    # at least MIN_DAY_RATIO of the typical postings for that weekday among active days.
    daily = df.groupby("date").size().rename("n").to_frame()
    daily["weekday"] = daily.index.weekday
    daily["active"] = daily["n"] >= 0.25 * daily["n"].quantile(0.9)
    typical = daily[daily["active"]].groupby("weekday")["n"].median()
    daily["typical"] = daily["weekday"].map(typical)
    daily["complete"] = daily["active"] & (daily["n"] >= MIN_DAY_RATIO * daily["typical"])
    df["day_complete"] = df["date"].map(daily["complete"])
    df.attrs["daily"] = daily
    return df.reset_index(drop=True)


def period_start(dates: pd.Series, freq: str) -> pd.Series:
    """Start date of the week (Sunday) or month each date belongs to."""
    if freq == "week":
        return dates.dt.to_period(WEEK_ANCHOR).dt.start_time
    return dates.dt.to_period("M").dt.start_time


def complete_dates(df: pd.DataFrame) -> pd.Series:
    """Dates (one per day) that are complete in the FULL data set."""
    return pd.Series(sorted(df.loc[df["day_complete"], "date"].unique()))


def _expected_days(start: pd.Timestamp, freq: str) -> int:
    return 7 if freq == "week" else start.days_in_month


def _prepared(df: pd.DataFrame, freq: str, dates: pd.Series | None) -> pd.DataFrame:
    """Rows on complete days, with a `period` column. Pass `dates` (from the full data) when `df`
    is a filtered subset."""
    mask = df["day_complete"] if dates is None else df["date"].isin(dates)
    d = df[mask].copy()
    d["period"] = period_start(d["date"], freq)
    return d


def period_metrics(df: pd.DataFrame, freq: str = "week", dates: pd.Series | None = None) -> pd.DataFrame:
    """One row per week/month using complete days only.

    `dates`: complete dates of the FULL data (use complete_dates(full_df)) when `df` is a filtered subset,
    so that period coverage is judged on days, not on whether the subset had postings that day.
    """
    d = _prepared(df, freq, dates)
    all_days = pd.Series(d["date"].unique()) if dates is None else pd.Series(dates)
    days_per_period = all_days.groupby(period_start(pd.to_datetime(all_days), freq)).nunique()
    g = d.groupby("period")
    out = pd.DataFrame({
        "postings": g.size(),
        "hourly_share_pct": g["is_hourly"].mean() * 100,
        "median_hourly_rate": g["hourly_mid"].median(),
        "mean_hourly_rate": g["hourly_mid"].mean(),
        "median_fixed_budget": g["fixed_budget"].median(),
        "mean_fixed_budget": g["fixed_budget"].mean(),
        "countries": g["country"].nunique(),
        "us_share_pct": g["country"].apply(lambda s: (s == "United States").mean() * 100),
        "remote_per10k": g["is_remote"].mean() * 1e4,
        "ai_ml_share_pct": g["role"].apply(lambda s: (s == "AI / ML engineer").mean() * 100),
    }).reindex(days_per_period.index)
    out["days_covered"] = days_per_period
    out["postings"] = out["postings"].fillna(0)
    out["postings_per_day"] = out["postings"] / out["days_covered"]
    out["expected_days"] = [_expected_days(p, freq) for p in out.index]
    out["is_full_period"] = out["days_covered"] == out["expected_days"]
    out.index.name = "period"
    return out


def role_share(df: pd.DataFrame, freq: str = "week", dates: pd.Series | None = None,
               total_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Role x period table: percent of all postings (complete days only), 'Other' excluded.

    For a filtered `df`, pass the unfiltered data as `total_df` to keep shares relative to ALL postings.
    """
    d = _prepared(df, freq, dates)
    totals = _prepared(total_df if total_df is not None else df, freq, dates).groupby("period").size()
    counts = d.groupby(["role", "period"]).size().unstack(fill_value=0).reindex(columns=totals.index, fill_value=0)
    share = counts / totals * 100
    return share.drop(index="Other") if "Other" in share.index else share


def country_share(df: pd.DataFrame, freq: str = "week", dates: pd.Series | None = None) -> pd.DataFrame:
    """Country x period table: percent of postings (complete days only), 'Unknown' excluded."""
    d = _prepared(df, freq, dates)
    totals = d.groupby("period").size()
    counts = d.groupby(["country", "period"]).size().unstack(fill_value=0)
    share = counts / totals * 100
    return share.drop(index="Unknown") if "Unknown" in share.index else share


def signal_trends(df: pd.DataFrame, freq: str = "week", dates: pd.Series | None = None) -> pd.DataFrame:
    """Share (per 10,000 postings) of titles mentioning each work-arrangement signal."""
    d = _prepared(df, freq, dates)
    rows = {name: d["title_clean"].str.contains(pat.pattern, regex=True).groupby(d["period"]).mean() * 1e4
            for name, pat in SIGNAL_PATTERNS.items()}
    return pd.DataFrame(rows)
