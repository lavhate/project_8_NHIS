# Job Market Dashboard (Task 6, Streamlit)

Tracks how the Upwork job market changes week by week and month by month.

## Layout

```
job_market_dashboard/
├── dashboard.py          # the Streamlit app
├── market_metrics.py     # data cleaning + metrics (also used by the notebook)
├── roles.py              # rule-based role labels (same as Task 3)
├── test_dashboard.py     # automated tests
├── requirements.txt
└── data/                 # put the Upwork CSV export(s) here
```

## Run

```bash
cd job_market_dashboard
pip install -r requirements.txt
# copy all_upwork_jobs_YYYY-MM-DD-YYYY-MM-DD.csv into the data/ folder
streamlit run dashboard.py            # opens http://localhost:8501
python test_dashboard.py              # optional: run the tests
```

The CSV is also found in the project folder (one level up), in an extra folder you type into the sidebar, or via the `JOBS_CSV` environment variable. The first load takes about 30 seconds and is then cached.

## Monthly update

1. Copy the new export (for example `all_upwork_jobs_2024-03-25-2024-04-30.csv`) into `data/`.
2. Click **Reload data** (a changed or new file is also detected on the next page refresh).
3. All files are combined and duplicate postings are removed, so overlapping exports are fine.

## What it shows

- **KPI row:** postings per day, hourly share, mean hourly rate, mean fixed budget, remote mentions per 10,000 titles, AI/ML share; latest full period vs the previous one.
- **Tabs:** Overview (trend charts and table), Roles (share by role, biggest movers), Geography (country shares, US share, countries active), Work signals (remote, long-term, full/part time, and others), Data notes (coverage and excluded days).
- **Controls:** weekly or monthly, role filter, client country, show or hide partial periods.

## Rules used

- A day counts only if it has at least half the postings typical for that weekday; partial days (collection gaps, first/last day of an export) are excluded.
- Weeks run Sunday to Saturday. A week or month is **full** only if every day in it is complete; others are drawn in grey.
- Rates are the midpoint of the posted hourly range (currency is not stated); the top 1% of rates and budgets is removed.

## Limitations

- With the supplied export there are only 5 full weeks and no full month, so changes of a few percent are usually noise. Use the dashboard for monitoring; it does not prove trends.
- There is no remote / on-site field; the "remote" line counts titles that mention it.
- The dashboard only shows what the CSV contains; it does not fetch new data by itself.
