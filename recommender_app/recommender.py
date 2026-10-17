"""Content-based job recommender over Upwork posting titles.

How it works
------------
1. Load the CSV, clean it (same rules as Step 2 of the notebook) and keep the dense
   posting window (from 2024-02-12).
2. Build a TF-IDF matrix over the UNIQUE cleaned titles (word 1-2 grams).
3. For a query (skills / job keywords) compute cosine similarity to every title.
4. Apply the user's filters at posting level (job type, pay, country, recency, excluded words).
5. Keep one result per title (the most recent matching posting), rank by similarity.

Data limits: only titles are available (no descriptions), so similarity is lexical.
"""
from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from roles import assign_role

DENSE_START = "2024-02-12"      # earlier rows are sparse stragglers (see notebook Step 2)
MAX_EXCLUDE_TERMS = 5

# Spanish phrases / non-Latin scripts create junk keywords, so they are not indexed.
_SPANISH = set("para de la el los las y en un una con por nuestro trabajo que se del al es".split())
# Only articles/prepositions are removed; words like "it", "ai", "c" are kept on purpose.
_STOP = ["a", "an", "and", "the", "for", "of", "to", "in", "on", "with", "or", "at", "by"]
_TOKEN = r"(?u)[a-z0-9+#]+"


def clean_title(text: str) -> str:
    """Lowercase, expand a few abbreviations, strip punctuation (keeps c++ and c#)."""
    t = str(text).lower()
    t = re.sub(r"\bsr\.?\b", "senior", t)
    t = re.sub(r"\bjr\.?\b", "junior", t)
    t = re.sub(r"\bva\b", "virtual assistant", t)
    t = re.sub(r"[^a-z0-9+#\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _num(x):
    """NaN -> None, numpy numbers -> plain float (for JSON)."""
    return None if x is None or pd.isna(x) else float(x)


class JobRecommender:
    def __init__(self, csv_path, dense_start: str = DENSE_START, verbose: bool = True):
        t0 = time.time()
        self._load(csv_path, dense_start)
        self._build_index()
        if verbose:
            print(f"[recommender] {len(self.df):,} postings, {len(self.titles):,} unique titles, "
                  f"{len(self.vectorizer.vocabulary_):,} terms, ready in {time.time() - t0:.1f}s")

    # ------------------------------------------------------------------ loading
    def _load(self, csv_path: str, dense_start: str) -> None:
        df = pd.read_csv(csv_path)
        df = df.dropna(subset=["title", "published_date"]).copy()
        df["published_date"] = pd.to_datetime(df["published_date"], utc=True, errors="coerce")
        df = df.dropna(subset=["published_date"])
        df = df[df["published_date"] >= pd.Timestamp(dense_start, tz="UTC")]
        df = df.drop_duplicates(subset=["title", "published_date"])

        df["title_clean"] = df["title"].map(clean_title)
        spanish = df["title_clean"].map(lambda s: sum(w in _SPANISH for w in s.split()) >= 2)
        non_latin = df["title"].map(lambda s: any(ord(ch) > 591 for ch in s))
        df = df[~(spanish | non_latin) & (df["title_clean"].str.len() > 2)]

        df["country"] = df["country"].fillna("Unknown")
        df["is_hourly"] = df["is_hourly"].astype(bool)
        self.df = df.reset_index(drop=True)

        # numpy views used by the fast filter / ranking code
        self._hourly = self.df["is_hourly"].to_numpy()
        self._low = self.df["hourly_low"].to_numpy(dtype=float)
        self._high = self.df["hourly_high"].to_numpy(dtype=float)
        self._budget = self.df["budget"].to_numpy(dtype=float)
        self._ts = self.df["published_date"].astype("int64").to_numpy()
        self._newest = self.df["published_date"].max()
        self._country_lower = self.df["country"].str.lower().to_numpy()
        self.countries = self.df["country"].value_counts()

    # ------------------------------------------------------------------ index
    def _build_index(self) -> None:
        self.titles, self.row_to_title = np.unique(self.df["title_clean"].to_numpy(), return_inverse=True)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, stop_words=_STOP,
            token_pattern=_TOKEN, lowercase=False, dtype=np.float32,
        )
        self.X = self.vectorizer.fit_transform(self.titles)            # (unique titles x terms), L2-normalised
        self._titles_series = pd.Series(self.titles)

    # ------------------------------------------------------------------ filters
    def _filter_mask(self, job_type, min_hourly, max_hourly, min_budget,
                     countries, posted_within_days, exclude_terms) -> np.ndarray:
        mask = np.ones(len(self.df), dtype=bool)
        hourly = self._hourly

        if job_type == "hourly":
            mask &= hourly
        elif job_type == "fixed":
            mask &= ~hourly

        # Pay filters only constrain the matching job type; postings with NO listed pay
        # are excluded when the filter is set (NaN comparisons are False).
        if min_hourly is not None:
            top = np.fmax(self._high, self._low)
            mask &= (~hourly) | (top >= min_hourly)
        if max_hourly is not None:
            bottom = np.fmin(self._low, self._high)
            mask &= (~hourly) | (bottom <= max_hourly)
        if min_budget is not None:
            mask &= hourly | (self._budget >= min_budget)

        if countries:
            wanted = {c.lower() for c in countries}
            unknown = wanted - set(self._country_lower)
            if unknown:
                raise ValueError(f"unknown country: {sorted(unknown)}")
            mask &= np.isin(self._country_lower, list(wanted))

        if posted_within_days is not None:
            cutoff = (self._newest - pd.Timedelta(days=posted_within_days)).value
            mask &= self._ts >= cutoff

        for term in exclude_terms or []:
            term = clean_title(term)
            if term:
                bad = self._titles_series.str.contains(rf"\b{re.escape(term)}\b", regex=True).to_numpy()
                mask &= ~bad[self.row_to_title]
        return mask

    # ------------------------------------------------------------------ main API
    def recommend(self, query: str, top_n: int = 10, job_type: str = "any",
                  min_hourly: float | None = None, max_hourly: float | None = None,
                  min_budget: float | None = None, countries: list[str] | None = None,
                  posted_within_days: int | None = None,
                  exclude_terms: list[str] | None = None) -> list[dict]:
        """Return up to `top_n` postings, one per distinct title, best match first.

        Raises ValueError for invalid arguments (empty query, bad job_type/top_n, unknown country).
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if job_type not in ("any", "hourly", "fixed"):
            raise ValueError("job_type must be 'any', 'hourly' or 'fixed'")
        if not isinstance(top_n, int) or isinstance(top_n, bool) or not 1 <= top_n <= 100:
            raise ValueError("top_n must be an integer between 1 and 100")
        if min_hourly is not None and max_hourly is not None and min_hourly > max_hourly:
            raise ValueError("min_hourly cannot be greater than max_hourly")
        if len(exclude_terms or []) > MAX_EXCLUDE_TERMS:
            raise ValueError(f"at most {MAX_EXCLUDE_TERMS} exclude_terms are allowed")
        q = clean_title(query)
        qv = self.vectorizer.transform([q])
        if qv.nnz == 0:
            return []                                              # no query word is in the vocabulary

        sims_title = (self.X @ qv.T).toarray().ravel()             # cosine similarity per unique title
        mask = self._filter_mask(job_type, min_hourly, max_hourly, min_budget,
                                 countries, posted_within_days, exclude_terms)

        rows = np.flatnonzero(mask & (sims_title[self.row_to_title] > 0))
        if rows.size == 0:
            return []

        rows = rows[np.argsort(-self._ts[rows], kind="stable")]   # newest first
        t_ids = self.row_to_title[rows]
        uniq_t, first = np.unique(t_ids, return_index=True)        # first hit = newest posting of that title
        best_rows = rows[first]
        n_similar = np.bincount(t_ids, minlength=len(self.titles))[uniq_t]
        scores = sims_title[uniq_t]

        order = np.lexsort((-self._ts[best_rows], -scores))[:top_n]   # score desc, then newest
        q_terms = set(q.split())

        results = []
        for k in order:
            r = self.df.iloc[best_rows[k]]
            results.append({
                "title": r["title"],
                "role": assign_role(r["title_clean"]),
                "job_type": "hourly" if r["is_hourly"] else "fixed",
                "hourly_low": _num(r["hourly_low"]),
                "hourly_high": _num(r["hourly_high"]),
                "budget": _num(r["budget"]),
                "country": r["country"],
                "posted_at": r["published_date"].isoformat(),
                "link": r["link"],
                "score": round(float(scores[k]), 4),
                "matched_terms": sorted(q_terms & set(r["title_clean"].split())),
                "similar_postings": int(n_similar[k]),
            })
        return results

    # ------------------------------------------------------------------ metadata
    def meta(self) -> dict:
        return {
            "postings": int(len(self.df)),
            "unique_titles": int(len(self.titles)),
            "date_range": [self.df["published_date"].min().isoformat(), self._newest.isoformat()],
            "hourly_share": round(float(self._hourly.mean()), 3),
            "countries": [{"name": c, "postings": int(n)} for c, n in self.countries.items()],
        }
