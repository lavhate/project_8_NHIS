"""Tests for the metrics module and the Streamlit dashboard. Run: python test_dashboard.py"""
import glob
import os

import market_metrics as mm

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = next(iter(sorted(glob.glob(os.path.join(HERE, "data", "all_upwork_jobs_*.csv"))
                       + glob.glob(os.path.join(HERE, "..", "data", "all_upwork_jobs_*.csv"))
                       + glob.glob(os.path.join(HERE, "..", "all_upwork_jobs_*.csv"))
                       + [p for p in [os.environ.get("JOBS_CSV")] if p])))
JOBS = mm.load_jobs([CSV])


def test_partial_days_are_excluded():
    daily = JOBS.attrs["daily"]
    assert not daily.loc["2024-02-15", "complete"] and not daily.loc["2024-03-24", "complete"]
    assert daily.loc["2024-02-20", "complete"]


def test_weekly_metrics_shape_and_flags():
    w = mm.period_metrics(JOBS, "week")
    full = w[w["is_full_period"]]
    assert len(full) == 5 and (full["days_covered"] == 7).all()
    assert full["postings_per_day"].between(5000, 7500).all()
    assert (w["days_covered"] <= 7).all()


def test_monthly_periods_are_flagged_partial():
    m = mm.period_metrics(JOBS, "month")
    assert not m["is_full_period"].any()


def test_filtered_subset_keeps_period_coverage():
    cd = mm.complete_dates(JOBS)
    sub = JOBS[JOBS["role"] == "Video editor"]
    w = mm.period_metrics(sub, "week", dates=cd)
    assert w["is_full_period"].sum() == 5
    share = mm.role_share(sub, "week", dates=cd, total_df=JOBS)
    assert list(share.index) == ["Video editor"] and share.max().max() < 10


def test_duplicate_files_are_deduplicated():
    twice = mm.load_jobs([CSV, CSV])
    assert len(twice) == len(JOBS)


def test_dashboard_runs_without_errors():
    from streamlit.testing.v1 import AppTest
    os.environ["JOBS_CSV"] = CSV
    at = AppTest.from_file(os.path.join(HERE, "dashboard.py"), default_timeout=300).run()
    assert not at.exception
    assert len(at.metric) == 6                                   # KPI row
    at.sidebar.radio[0].set_value("Monthly").run()               # switch granularity
    assert not at.exception
    at.sidebar.radio[0].set_value("Weekly").run()
    at.sidebar.multiselect[0].set_value(["Video editor"]).run()  # role filter
    assert not at.exception and len(at.metric) == 6


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\nAll {len(tests)} tests passed")
