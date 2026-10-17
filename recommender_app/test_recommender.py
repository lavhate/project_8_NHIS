"""Tests for the recommender and the Streamlit page.

Run:  python test_recommender.py          (or: pytest -q test_recommender.py)
Needs the CSV in the project folder, or the JOBS_CSV environment variable.
"""
import os

import pandas as pd

from recommender import JobRecommender

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_NAME = "all_upwork_jobs_2024-02-07-2024-03-24.csv"
CSV = next(p for p in (os.environ.get("JOBS_CSV"), os.path.join(HERE, "..", CSV_NAME), os.path.join(HERE, "..", "data", CSV_NAME), os.path.join(HERE, CSV_NAME))
           if p and os.path.exists(p))
REC = JobRecommender(CSV, verbose=False)


def test_relevant_deduplicated_and_sorted():
    out = REC.recommend("react developer", top_n=10)
    assert len(out) == 10
    titles = [r["title"].lower() for r in out]
    assert len(set(titles)) == len(titles)
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)
    assert all("react" in t or "developer" in t for t in titles)


def test_job_type_and_pay_filters():
    hourly = REC.recommend("web developer", job_type="hourly", min_hourly=30, top_n=30)
    assert hourly and all(r["job_type"] == "hourly" and max(r["hourly_low"] or 0, r["hourly_high"] or 0) >= 30 for r in hourly)
    fixed = REC.recommend("logo design", job_type="fixed", min_budget=500, top_n=30)
    assert fixed and all(r["job_type"] == "fixed" and r["budget"] >= 500 for r in fixed)


def test_country_recency_and_exclusion():
    us = REC.recommend("video editor", countries=["united states"], top_n=20)
    assert us and all(r["country"] == "United States" for r in us)
    recent = REC.recommend("video editor", posted_within_days=2, top_n=20)
    assert all((REC._newest - pd.Timestamp(r["posted_at"])).days <= 2 for r in recent)
    ex = REC.recommend("assistant", exclude_terms=["virtual"], top_n=30)
    assert all("virtual" not in r["title"].lower() for r in ex)


def test_no_match_gives_empty_list():
    assert REC.recommend("zzqxjv") == []


def test_invalid_arguments_raise():
    for kwargs in ({"query": "  "}, {"query": "dev", "top_n": 0}, {"query": "dev", "job_type": "weekly"},
                   {"query": "dev", "min_hourly": 50, "max_hourly": 10}, {"query": "dev", "countries": ["Atlantis"]}):
        try:
            REC.recommend(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {kwargs}")


def test_streamlit_page_runs_without_errors():
    from streamlit.testing.v1 import AppTest
    os.environ["JOBS_CSV"] = CSV
    at = AppTest.from_file(os.path.join(HERE, "streamlit_app.py"), default_timeout=180).run()
    assert not at.exception
    at.text_area(key="query").set_value("react node js developer")
    at.button(key="search").click().run()
    assert not at.exception
    assert any("recommendation" in s.value for s in at.subheader)
    at.sidebar.radio[0].set_value("hourly").run()                       # filter change re-runs cleanly
    assert not at.exception


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\nAll {len(tests)} tests passed")
