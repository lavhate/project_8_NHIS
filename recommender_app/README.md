# Job Recommender (Task 5, Streamlit)

A content-based job recommendation engine over Upwork job postings, with a Streamlit web app.

## Project layout

```
project/
├── job_market_analysis.ipynb                      # notebook (Tasks 1-5)
├── all_upwork_jobs_2024-02-07-2024-03-24.csv      # put the dataset here
└── recommender_app/
    ├── streamlit_app.py     # the web app (user interface)
    ├── recommender.py       # recommendation engine (TF-IDF + filters)
    ├── roles.py             # rule-based role labels (same rules as Task 3)
    ├── test_recommender.py  # automated tests
    ├── requirements.txt
    └── README.md
```

## Setup and run

```bash
cd recommender_app
pip install -r requirements.txt
streamlit run streamlit_app.py        # opens http://localhost:8501
python test_recommender.py            # optional: run the automated tests
```

The first start takes about 10 seconds (it builds the search index once and then caches it). If the CSV is somewhere else, set `JOBS_CSV` or type the path into the page when it asks:

```bash
# Windows PowerShell
$env:JOBS_CSV = "C:\path\to\all_upwork_jobs_2024-02-07-2024-03-24.csv"
# Linux / macOS
export JOBS_CSV=/path/to/all_upwork_jobs_2024-02-07-2024-03-24.csv
```

## Using the app

1. Type your skills or the kind of work you want (or click an example).
2. Optionally set the filters in the sidebar: job type, min/max hourly rate, min fixed budget, client country, posted within, words to exclude, number of results.
3. Read the results as cards or as a table, and download them as CSV.

## How the engine works

1. Load the CSV, clean it (drop duplicates, Spanish/non-Latin titles, keep postings from 2024-02-12 onward).
2. Build a TF-IDF matrix (words and word pairs) over the unique cleaned titles.
3. Compare the user's text with every title using cosine similarity.
4. Apply filters at posting level, keep one result per distinct title (the newest posting), and rank by similarity (ties: newest first).

A search takes about 20-40 ms after the index is built.

## Python interface (for the notebook or other code)

Streamlit provides the user interface only; it does not expose a REST API. The engine itself is a plain Python class:

```python
from recommender import JobRecommender

rec = JobRecommender("all_upwork_jobs_2024-02-07-2024-03-24.csv")
results = rec.recommend("python data scraping", top_n=5, job_type="hourly", min_hourly=20)
```

`JobRecommender.recommend(query, top_n=10, job_type="any", min_hourly=None, max_hourly=None, min_budget=None, countries=None, posted_within_days=None, exclude_terms=None)` returns a list of dictionaries, best match first.

| Argument | Type | Default | Description |
|---|---|---|---|
| `query` | str | required | Skills or job keywords. |
| `top_n` | int | 10 | Number of results, 1 to 100. |
| `job_type` | str | `"any"` | `"any"`, `"hourly"` or `"fixed"`. |
| `min_hourly` | float | None | Keep hourly postings whose top rate is at least this ($/h). Fixed-price postings are not affected. |
| `max_hourly` | float | None | Keep hourly postings whose lowest rate is at most this ($/h). |
| `min_budget` | float | None | Keep fixed-price postings with a budget of at least this. Hourly postings are not affected. |
| `countries` | list[str] | None | Country names, case-insensitive (see `rec.meta()["countries"]`). |
| `posted_within_days` | int | None | Postings from the last N days, counted back from the **newest posting in the data**. |
| `exclude_terms` | list[str] | None | Drop titles containing any of these words/phrases (max 5). |

If a pay filter is set, postings **without** a listed rate/budget are excluded. Invalid input raises `ValueError`.

Each result contains:

| Field | Meaning |
|---|---|
| `title` | Original posting title. |
| `role` | Role label from the rule-based taxonomy (`"Other"` if no rule matches). |
| `job_type`, `hourly_low`, `hourly_high`, `budget` | Pay as listed; unused fields are `None`. Currency is not stated in the data. |
| `country` | Country field from the data (most likely the client's location). |
| `posted_at` | Posting time (ISO 8601, UTC). |
| `link` | Link to the posting. |
| `score` | Cosine similarity between 0 and 1. |
| `matched_terms` | Query words that appear in the title. |
| `similar_postings` | Number of postings with the same title that pass your filters. |

An empty list means no posting matched (for example none of the query words occur in any title). `rec.meta()` returns dataset information (posting count, date range, countries).

## Limitations

- **Titles only:** no job descriptions, skills lists or user history, so matching is by words, not meaning (for example "dev" will not match "developer").
- **No personalisation over time:** no user accounts or feedback, so every search is independent.
- **Currency unknown:** rates are shown as listed.
- **Snapshot data:** about six weeks (Feb to Mar 2024), so postings are old and links may have expired.
- **Offline accuracy check is a proxy:** see section 5C of the notebook.

## Ideas for improvement

- Semantic embeddings (for example a sentence-transformer model) so related wording matches.
- Collect clicks/saves and learn a ranking model.
- Add a small synonym list (dev/developer, js/javascript).
