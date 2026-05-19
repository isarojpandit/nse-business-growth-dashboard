# NSE Business Growth Dashboard

![CI](https://github.com/isarojpandit/nse-business-growth-dashboard/actions/workflows/ci.yml/badge.svg)
![Monthly NSE Update](https://github.com/isarojpandit/nse-business-growth-dashboard/actions/workflows/monthly_nse_update.yml/badge.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-Live%20App-red?logo=streamlit)
![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)

A production-ready Streamlit dashboard for analyzing NSE business growth across major market segments using automated data scraping, cleaning, normalization, SQLite storage, and interactive visual analytics.

## Live Demo

**Streamlit App:**  
https://nse-business-growth-dashboard.streamlit.app/

**GitHub Repository:**  
https://github.com/isarojpandit/nse-business-growth-dashboard

---

## Project Overview

The NSE Business Growth Dashboard is designed to automate the analysis of NSE monthly business growth data across multiple market segments.

The dashboard tracks historical monthly data for:

1. Capital Market  
2. Equity Derivatives  
3. Currency Derivatives  
4. Interest Rate Derivatives  

The project started as an Excel-based manual dashboard and was converted into an automated Python-based data pipeline with Streamlit visualization.

The dashboard currently focuses on monthly and quarterly business growth analysis. Daily-level analytics can be added in future as an advanced insight layer.

---

## Key Features

- Automated NSE historical data scraping
- Monthly NSE data update pipeline
- Data normalization across multiple NSE segments
- SQLite database integration
- Streamlit interactive dashboard
- Monthly and quarterly trend analysis
- MoM and QoQ change analysis
- Moving average controls
- Comparative segment analysis
- Indexed growth comparison
- Data quality summary
- GitHub Actions CI workflow
- Monthly update workflow structure

---

## Market Segments Covered

| Segment | Instrument |
|---|---|
| Capital Market | NA |
| Equity Derivatives | Futures |
| Equity Derivatives | Options |
| Currency Derivatives | Futures |
| Currency Derivatives | Options |
| Interest Rate Derivatives | NA |

---

## Data Source

The data is collected from NSE business growth pages:

| Segment | NSE Page |
|---|---|
| Capital Market | Business Growth in CM Segment |
| Equity Derivatives | Business Growth in F&O Segment |
| Currency Derivatives | Business Growth in Currency Derivatives Segment |
| Interest Rate Derivatives | Business Growth in Interest Rate Derivatives Segment |

The pipeline extracts monthly tables from NSE pages and converts them into a common dashboard-ready structure.

---

## Important Data Logic

The dashboard follows the existing Excel table logic.

### Turnover

Turnover is treated as:

```text
Average Daily Turnover = Monthly Turnover / Trading Days
