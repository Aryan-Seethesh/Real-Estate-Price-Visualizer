### PRD — Real Estate Price Visualizer (PySide6 + PostgreSQL)

#### 1) Overview
- **Goal**: Compare area-wise property prices and trends with a polished, modern UI.
- **Stack constraints**: Python-only modules/frameworks. No non-Python tech.
- **Infra**: PostgreSQL for persistent storage; minimal dependencies.

#### 2) Users
- **Student/learner**, **home buyer**, **owner/agent** needing quick locality comparisons.

#### 3) Scope (Core)
- **Inputs**:
- PostgreSQL database (`PG* env vars`).
  - Data Manager: seed 100 Indian cities (includes Navi Mumbai) with synthetic listings when empty.
  - Import real data via URL to a CSV file (Python requests). Required columns: `city, locality, property_type, bhk, area_sqft, total_price, listed_date, source`.
- **Outputs**:
  - Median price per sqft (ppsf) by city/locality.
  - Time-series of median ppsf by selected granularity (Monthly or Daily).
  - Compare up to 3 localities.
- **Views**:
  - Dashboard with filters (city, locality, property type, BHK, date range, price range, area range, granularity).
  - Charts: line (trend), bar (comparison), histogram (price), box plot (ppsf by type).
- **Data quality**:
  - Type coercion and validity checks in ingestion.
  - Outlier removal via IQR on ppsf per locality.
- **Out of scope (Core)**:
  - Automated multi-site scraping, ML predictions.

#### 4) Tech Stack (Python-Only)
- **UI**: Streamlit (single-file app)
- **Charts**: Plotly Express
- **Data**: Pandas for cleaning/aggregations
- **Storage**: PostgreSQL via `psycopg2`
- **Optional map**: Folium (future)

#### 5) Dependencies
- streamlit
- pandas, numpy
- plotly
- sqlite3 (stdlib)
- requests (for URL CSV ingestion)
- folium (optional later)

#### 6) Folder Structure
- app/
  - app.py
  - db.py
  - utils.py
  - requirements.txt
  - README.md

#### 7) Core Features
- **Load data**: Read from SQLite. Data Manager to seed or import by URL.
- **Clean**:
  - Compute `ppsf = total_price / area_sqft`.
  - Drop invalid rows; remove outliers via IQR per locality.
  - Parse `listed_date` and derive `listed_month`.
- **Aggregate**:
  - By city/locality: `median_ppsf`, `p25_ppsf`, `p75_ppsf`, `listing_count`.
  - Time-series: `median_ppsf` by month or day.
- **Filters**:
  - city, locality (multi-select), property_type (Apartment, Penthouse, Studio, RK, Villa, etc.), bhk, date range (slider), price range, area range, granularity switch (Monthly/Daily).
- **Visualize**:
  - Line (trend), bar (comparison), histogram (price), box (ppsf by type) with dark, modern styling.

#### 8) Nice-to-Have (Future)
- Folium map: one marker per locality, color by median_ppsf.
- Confidence score using listing_count and variability.
- Auto-refresh and scheduled URL ingestions.

#### 9) Data Model
- Base table: `listing(city_id, locality_id, property_type, bhk, area_sqft, total_price, listed_date, source)`; FKs to `city` and `locality`.
- View: `listing_view` exposes `city`, `locality`, `ppsf`, `listed_date`, `listed_month`.
- Derived columns: `ppsf`, `listed_month (YYYY-MM)`.

#### 10) Functional Requirements
- Seed 100+ cities on first run if DB empty.
- Ingest CSV from URL with required columns.
- Filter panel updates charts within 1–2 seconds on a laptop.
- Compare up to 3 localities.
- Show listing_count and date range used in aggregates.

#### 11) Non-Functional
- Runs locally with `streamlit run app/app.py`.
- Works with datasets up to ~200k rows on 8GB RAM.
- Clear messages when URL ingestion fails or columns are missing.

#### 12) Compliance Note
- Use publicly available CSVs or authorized datasets for URL ingestion.
- If adding scraping later, read site T&Cs and respect robots.txt; keep QPS very low.

#### 13) Milestones
- M1: SQLite schema, seeding 100 cities, listing view.
- M2: Filters (city/locality/type/bhk/ranges), daily/monthly granularity.
- M3: Charts (line, bar, histogram, box), dark UI theme.
- M4: Data Manager (seed + import URL), docs update.

#### 14) Acceptance Criteria
- First run with empty DB seeds 100 cities (incl. Navi Mumbai) and synthetic listings.
- User can import real data via a CSV URL.
- User selects city/locality → sees median ppsf trend for chosen granularity (Monthly/Daily).
- User compares up to 3 localities in a bar chart with listing counts.
- Filters (type, bhk, date, price, area) work and update charts quickly.
- App runs with a single `streamlit run` command.

#### 15) Setup Instructions (to include in README.md)
- Create venv; install requirements:
  - pip install -r requirements.txt
- Run:
  - streamlit run app/app.py
- Put CSVs in `app/data/` with required columns.

- Prediction: simple linear trend extrapolation for each locality.
- Add a simple “confidence score” using listing_count and variability.
- Minimal ingestion script to fetch a static CSV from a URL.




