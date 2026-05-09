import sqlite3
from pathlib import Path

DB_PATH = Path("data/nse_business_growth.db")

def init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nse_business_growth (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        segment TEXT NOT NULL,
        instrument TEXT,
        year INTEGER,
        month TEXT,
        quarter TEXT,
        turnover REAL,
        volume REAL,
        mom_turnover_change REAL,
        mom_volume_change REAL,
        qoq_turnover_change REAL,
        qoq_volume_change REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

    print("SQLite database created successfully!")
    print(f"Database path: {DB_PATH}")

if __name__ == "__main__":
    init_database()