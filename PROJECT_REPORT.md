# NSE Business Growth Dashboard — Project Report

## 1. Project Title

**NSE Business Growth Dashboard**

An automated data pipeline and interactive dashboard for analyzing National Stock Exchange of India (NSE) business growth across major market segments.

---

## 2. Project Objective

The objective of this project is to convert a manually maintained Excel-based NSE business growth dashboard into an automated, scalable, and interactive data analytics system.

The project automates the complete workflow:

```text
NSE Website
→ Data Scraping
→ Data Cleaning
→ Data Normalization
→ CSV Storage
→ SQLite Database
→ Streamlit Dashboard
→ GitHub Actions Monthly Automation
```

The final dashboard helps users analyze monthly and quarterly business growth trends across NSE segments using interactive filters, moving averages, MoM/QoQ analysis, and comparative views.

---

## 3. Problem Statement

Earlier, NSE monthly business growth data was maintained manually in Excel. This approach had several limitations:

- Manual monthly data collection was time-consuming.
- Data cleaning and formatting had to be repeated.
- Different NSE segment tables had different structures.
- MoM and QoQ calculations were prone to manual errors.
- Long-term trend analysis was difficult.
- Dashboard updates were not automated.
- Deployment and sharing were limited.

This project solves these issues by building a Python-based automated data pipeline and deploying the output through a Streamlit dashboard.

---

## 4. Scope of the Project

The current project focuses on monthly and quarterly business growth analysis for the following NSE market segments:

| Segment | Instrument |
|---|---|
| Capital Market | NA |
| Equity Derivatives | Futures |
| Equity Derivatives | Options |
| Currency Derivatives | Futures |
| Currency Derivatives | Options |
| Interest Rate Derivatives | NA |

The current version uses monthly data as the main analytical layer. Daily-level analytics is planned as a future enhancement.

---

## 5. Data Source

The data is collected from NSE business growth pages available on the NSE website.

The scraper extracts monthly historical business growth tables from pages related to:

- Capital Market
- Equity Derivatives
- Currency Derivatives
- Interest Rate Derivatives

Since NSE pages are dynamic, the project uses **Playwright** instead of simple static HTML scraping.

---

## 6. Why Playwright Was Used

NSE pages load data dynamically through browser-rendered content. Static tools like `requests` and `pandas.read_html()` were not sufficient because many tables appeared empty or incomplete in raw HTML.

Playwright was used because it can:

- Open NSE pages like a real browser
- Wait for JavaScript-rendered tables
- Click financial year links
- Extract visible monthly tables
- Work in local and GitHub Actions environments

---

## 7. Data Processing Logic

The dashboard follows the existing Excel business logic.

### 7.1 Turnover Logic

Turnover is calculated as:

```text
Average Daily Turnover = Monthly Turnover / Trading Days
```

Turnover is shown in:

```text
₹ Crores
```

### 7.2 Volume Logic

Volume is calculated as:

```text
Average Daily Volume = Monthly Volume or Contracts / Trading Days
```

Volume unit depends on the segment:

| Segment | Volume Unit |
|---|---|
| Capital Market | Lakhs/day |
| Derivatives Segments | Contracts/day |

### 7.3 Options Turnover Logic

For options, the project uses:

```text
Premium Turnover
```

This was intentionally selected instead of notional turnover because premium turnover gives a more realistic view of actual option trading value.

---

## 8. Final Normalized Dataset Schema

The final processed dataset is stored at:

```text
data/processed/clean_nse_business_growth_from_nse.csv
```

The normalized schema contains the following columns:

| Column | Description |
|---|---|
| segment | NSE market segment |
| instrument | Instrument type |
| year | Calendar year |
| month_label | Month label such as Apr-2026 |
| month_date | Date representation of month |
| calendar_quarter | Calendar quarter |
| financial_year | Financial year |
| financial_quarter | Financial quarter |
| turnover | Average daily turnover |
| volume | Average daily volume |
| mom_turnover_change | Month-on-month turnover change |
| mom_volume_change | Month-on-month volume change |

---

## 9. Dataset Summary

The current normalized dataset contains approximately:

```text
1,154 rows
```

Segment-wise distribution:

| Segment | Instrument | Rows |
|---|---:|---:|
| Capital Market | NA | 313 |
| Currency Derivatives | Futures | 213 |
| Currency Derivatives | Options | 187 |
| Equity Derivatives | Futures | 133 |
| Equity Derivatives | Options | 133 |
| Interest Rate Derivatives | NA | 175 |

The row count may increase after future monthly updates.

---

## 10. Historical Data Range

The available data range differs by segment.

| Segment | Instrument | Start Month | Latest Month |
|---|---|---:|---:|
| Capital Market | NA | Apr-2000 | Apr-2026 |
| Currency Derivatives | Futures | Aug-2008 | Apr-2026 |
| Currency Derivatives | Options | Oct-2010 | Apr-2026 |
| Equity Derivatives | Futures | Apr-2015 | Apr-2026 |
| Equity Derivatives | Options | Apr-2015 | Apr-2026 |
| Interest Rate Derivatives | NA | Aug-2009 | Apr-2026 |

---

## 11. System Architecture

```text
NSE Website
    ↓
Playwright Scraper
    ↓
Raw Scraped Data
    ↓
Pandas Data Cleaning
    ↓
Normalized CSV
    ↓
SQLite Database
    ↓
Streamlit Dashboard
    ↓
GitHub Actions Automation
    ↓
Streamlit Cloud Deployment
```

---

## 12. Project Pipeline

### 12.1 Historical Scraping Pipeline

Script:

```text
scripts/scrape_nse_history.py
```

Purpose:

- Opens NSE segment pages
- Extracts all available financial years
- Clicks year-wise records
- Extracts monthly tables
- Stores raw scraped data

Output:

```text
data/raw/nse_scraped/
```

### 12.2 Historical Normalization Pipeline

Script:

```text
scripts/normalize_nse_history.py
```

Purpose:

- Reads raw scraped data
- Maps different segment structures into a common format
- Applies turnover and volume logic
- Adds financial year and financial quarter
- Calculates MoM changes
- Saves final normalized CSV

Output:

```text
data/processed/clean_nse_business_growth_from_nse.csv
```

### 12.3 SQLite Loading Pipeline

Script:

```text
scripts/load_nse_history_to_db.py
```

Purpose:

- Reads processed CSV
- Validates required columns
- Checks duplicate rows
- Loads data into SQLite database

Database path:

```text
data/nse_business_growth.db
```

SQLite table:

```text
nse_business_growth
```

### 12.4 Monthly Update Pipeline

Script:

```text
scripts/update_nse_monthly_data.py
```

Purpose:

- Scrapes latest NSE data
- Normalizes new monthly records
- Merges latest records with historical dataset
- Removes duplicates using segment, instrument, and month
- Recalculates MoM values
- Updates processed CSV

Duplicate key:

```text
segment + instrument + month_label
```

---

## 13. Dashboard Overview

The dashboard is built using Streamlit and Plotly.

It provides interactive analysis through the following pages:

1. Overview
2. Monthly Analysis
3. Quarterly Analysis
4. Comparative View
5. Data Quality

---

## 14. Dashboard Page Details

### 14.1 Overview Page

The Overview page provides selected segment-level business summary.

It includes:

- Latest month
- Latest turnover
- Latest volume
- Financial period
- Total turnover
- Average turnover
- Total volume
- Average volume
- Monthly insight statement
- Best and worst month summary
- Monthly trend charts

### 14.2 Monthly Analysis Page

The Monthly Analysis page includes:

- Monthly average turnover trend
- Monthly average volume trend
- Moving average overlay
- MoM turnover change
- MoM volume change

MoM charts use:

```text
Green bars = positive change
Red bars = negative change
```

Extreme MoM values are visually capped so that one large outlier does not make the whole chart unreadable.

### 14.3 Quarterly Analysis Page

The Quarterly Analysis page includes:

- Quarterly average turnover
- Quarterly average volume
- Quarterly moving average
- QoQ turnover change
- QoQ volume change

QoQ charts also use green and red bars for positive and negative changes.

### 14.4 Comparative View Page

The Comparative View allows comparison across segment/instrument pairs.

Supported comparison modes:

1. Absolute Value
2. Indexed Growth

Indexed Growth uses:

```text
Base = 100
```

This is useful because different NSE segments operate at different scales. For example, Equity Derivatives Options can be much larger than other segments, so absolute comparison can hide smaller segments. Indexed Growth makes growth comparison easier.

### 14.5 Data Quality Page

The Data Quality page includes:

- Total rows
- Duplicate key count
- Missing turnover count
- Missing volume count
- Segment/instrument summary
- Raw data preview

This helps verify whether the dataset is clean and dashboard-ready.

---

## 15. Dashboard Filters

The dashboard provides the following filters:

- Segment
- Instrument
- Financial Year
- Month
- Financial Quarter
- Time Range
- Moving Average Window
- MoM/QoQ Display Cap

### 15.1 Time Range Filter

Available options:

```text
Last 1 Year
Last 3 Years
Last 5 Years
Last 10 Years
Full History
```

This keeps charts readable when working with long historical data.

### 15.2 Moving Average Window

The moving average window supports continuous selection from:

```text
2 to 12
```

Moving average is applied only on trend charts, not MoM or QoQ change charts.

---

## 16. Important Visualization Decisions

### 16.1 Why Moving Average Is Not Used on MoM/QoQ Charts

Moving average is useful for actual level metrics such as turnover and volume.

MoM and QoQ are already change metrics. Adding moving average to them can make interpretation confusing.

Therefore:

```text
Trend charts = line chart + moving average
Change charts = bar chart + green/red color coding
```

### 16.2 Why MoM/QoQ Charts Are Capped

Some early months have very small previous-month values. This can cause very high percentage changes such as 500% or 1500%.

The calculation may be mathematically correct, but visually it can distort the chart.

To solve this:

- Actual value is preserved
- Display value is capped
- Tooltip shows the actual change

### 16.3 Why Indexed Growth Is Used

When comparing different segments, absolute values can be misleading because one large segment may dominate the chart.

Indexed Growth normalizes every selected series to 100 at the first selected period.

This helps answer:

```text
Which segment grew faster?
```

instead of only:

```text
Which segment is larger?
```

---

## 17. Automation

The project uses GitHub Actions for automation.

### 17.1 CI Workflow

Workflow file:

```text
.github/workflows/ci.yml
```

Purpose:

- Validate project setup
- Check if the dashboard pipeline can run
- Ensure basic project health

### 17.2 Monthly NSE Update Workflow

Workflow file:

```text
.github/workflows/monthly_nse_update.yml
```

Purpose:

- Run monthly NSE scraping script
- Update processed CSV
- Load data into SQLite
- Commit updated data files if changes exist
- Trigger Streamlit Cloud redeployment

Schedule:

```text
5th day of every month at 09:00 AM IST
```

GitHub cron uses UTC, so the workflow is scheduled accordingly.

---

## 18. Deployment

The dashboard is deployed on Streamlit Cloud.

Live app:

```text
https://nse-business-growth-dashboard.streamlit.app/
```

Deployment flow:

```text
GitHub Push
→ Streamlit Cloud detects change
→ App redeploys automatically
```

---

## 19. Repository Structure

```text
nse-business-growth-dashboard/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── monthly_nse_update.yml
│
├── config/
│   └── nse_sources.py
│
├── dashboard/
│   ├── app.py
│   └── components/
│       └── charts.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   │   └── clean_nse_business_growth_from_nse.csv
│   └── nse_business_growth.db
│
├── scripts/
│   ├── scrape_nse_history.py
│   ├── normalize_nse_history.py
│   ├── update_nse_monthly_data.py
│   ├── load_nse_history_to_db.py
│   ├── run_pipeline.py
│   └── view_database.py
│
├── src/
│   ├── ingestion/
│   ├── transformation/
│   ├── storage/
│   └── utils/
│
├── README.md
├── PROJECT_REPORT.md
├── requirements.txt
└── .gitignore
```

---

## 20. Tech Stack

| Area | Technology |
|---|---|
| Programming Language | Python |
| Data Processing | Pandas |
| Web Scraping | Playwright |
| Database | SQLite |
| Dashboard | Streamlit |
| Visualization | Plotly |
| Automation | GitHub Actions |
| Deployment | Streamlit Cloud |
| Version Control | Git and GitHub |

---

## 21. Validation and Data Quality

The project includes several validation checks:

- Required column validation
- Duplicate key validation
- Missing turnover validation
- Missing volume validation
- Segment/instrument row count check
- Historical data overwrite safety check
- MoM recalculation after update

The monthly update script prevents overwriting the main dataset if historical row counts unexpectedly reduce.

---

## 22. Challenges Faced

### 22.1 NSE Dynamic Website

NSE pages are dynamic and rendered through browser-side logic. Static scraping methods returned empty tables. Playwright was required to properly load and extract the tables.

### 22.2 Segment-Specific Table Structures

Each segment has different table structures. The project required separate mapping logic for:

- Capital Market
- Equity Derivatives
- Currency Derivatives
- Interest Rate Derivatives

### 22.3 Unit Differences

Capital Market volume is in lakhs, while derivatives volume is in contracts. The dashboard handles this using dynamic labels.

### 22.4 Large Historical Data

Full historical data creates dense charts. This was solved using:

- Time range filter
- Plotly zoom
- Range slider
- Moving average controls

### 22.5 Outlier Percentage Changes

MoM and QoQ percentages can become extremely large when the previous value is very small. Visual capping was added to keep charts readable.

### 22.6 GitHub Actions Environment

Local files were not initially available in the GitHub Actions runner. The processed CSV and SQLite database had to be tracked in the repository so the workflow could run successfully.

---

## 23. Results

The project successfully achieved:

- Historical NSE business growth data extraction
- Data normalization into a common schema
- SQLite-backed dashboard data storage
- Interactive Streamlit dashboard
- Monthly and quarterly analytics
- MoM and QoQ change analysis
- Comparative segment analysis
- Data quality monitoring
- GitHub Actions CI workflow
- Monthly automated update workflow
- Streamlit Cloud deployment

---

## 24. Business Value

This dashboard provides value by:

- Reducing manual Excel update effort
- Improving data consistency
- Enabling long-term historical analysis
- Supporting segment-wise comparison
- Providing interactive business insights
- Allowing automated monthly refresh
- Making dashboard sharing easier through Streamlit Cloud

---

## 25. Future Scope

### 25.1 Daily Data Analytics

The next major enhancement is to add daily data analysis.

Daily data can provide deeper insights such as:

- Daily turnover trends
- Daily volume trends
- Daily spike detection
- Expiry-week analysis
- Market activity volatility
- Top trading days
- Monthly consistency score
- Activity concentration ratio

### 25.2 Advanced Analytics

Possible future analytics:

- YoY comparison
- Segment contribution share
- Growth ranking
- Rolling volatility
- Anomaly detection
- Correlation between volume and turnover
- Automated PDF report generation

### 25.3 Automation Enhancements

Future automation improvements:

- Retry logic for NSE scraping
- Better error logs
- Workflow artifact upload on failure
- Slack or email failure alerts
- Monthly report notification
- Scraper health check

---

## 26. Conclusion

The NSE Business Growth Dashboard converts a manual Excel-based workflow into an automated, scalable, and interactive data analytics platform.

It provides a complete end-to-end solution:

```text
Data Collection
→ Data Cleaning
→ Data Normalization
→ Storage
→ Dashboard
→ Automation
→ Deployment
```

The project is suitable for NSE business growth monitoring, segment-wise performance analysis, long-term market activity tracking, and future advanced analytics.

---

## 27. Author

**Saroj Pandit**

GitHub:

```text
https://github.com/isarojpandit
```

Live Dashboard:

```text
https://nse-business-growth-dashboard.streamlit.app/
```