import os
from datetime import datetime
from typing import Iterable, List, Tuple, Optional, Dict, Any

import pandas as pd
import random
import requests
import sqlite3


def _sqlite_path() -> str:
    """Resolve path to SQLite database file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.normpath(os.path.join(base_dir, "../real_estate.db"))
    return os.getenv("SQLITE_DB_FILE", default_path)


def connect():
    """Connect to SQLite (file-based)."""
    db_path = _sqlite_path()
    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        # Better compatibility with pandas strings
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        raise RuntimeError("Failed to connect to SQLite DB at " + db_path + ". Details: " + str(e))


def init_schema(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS city (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS locality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(city_id, name),
            FOREIGN KEY(city_id) REFERENCES city(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            locality_id INTEGER NOT NULL,
            property_type TEXT NOT NULL,
            bhk INTEGER,
            area_sqft REAL NOT NULL,
            total_price REAL NOT NULL,
            listed_date TEXT NOT NULL,
            source TEXT,
            FOREIGN KEY(city_id) REFERENCES city(id) ON DELETE CASCADE,
            FOREIGN KEY(locality_id) REFERENCES locality(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()


def seed_cities_10(conn) -> None:
    """Insert exactly 10 cities if they do not already exist."""
    cities: List[str] = [
        "Mumbai", "Navi Mumbai", "Pune", "Delhi", "Bengaluru",
        "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Jaipur",
    ]
    cur = conn.cursor()
    for c in cities:
        cur.execute("INSERT OR IGNORE INTO city(name) VALUES (?)", (c,))
    conn.commit()


def ensure_locality(conn, city_name: str, locality_name: str) -> Tuple[int, int]:
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO city(name) VALUES (?)", (city_name,))
    cur.execute("SELECT id FROM city WHERE name = ?", (city_name,))
    city_id = cur.fetchone()[0]
    cur.execute(
        "INSERT OR IGNORE INTO locality(city_id, name) VALUES (?, ?)",
        (city_id, locality_name),
    )
    cur.execute("SELECT id FROM locality WHERE city_id = ? AND name = ?", (city_id, locality_name))
    locality_id = cur.fetchone()[0]
    conn.commit()
    return city_id, locality_id


def insert_listings(conn, rows: Iterable[Tuple[str, str, str, Optional[int], float, float, str, Optional[str]]]) -> int:
    cur = conn.cursor()
    to_insert: List[Tuple[int, int, str, Optional[int], float, float, str, Optional[str]]] = []
    for city, locality, property_type, bhk, area_sqft, total_price, listed_date, source in rows:
        city_id, locality_id = ensure_locality(conn, city, locality)
        to_insert.append((city_id, locality_id, property_type, bhk, area_sqft, total_price, listed_date, source))
    cur.executemany(
        """
        INSERT INTO listing (
            city_id, locality_id, property_type, bhk, area_sqft, total_price, listed_date, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        to_insert,
    )
    conn.commit()
    return cur.rowcount or 0


def import_csv_to_db(conn, csv_path: str) -> int:
    df = pd.read_csv(csv_path)
    expected = [
        "city", "locality", "property_type", "bhk", "area_sqft", "total_price", "listed_date", "source"
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    df["bhk"] = pd.to_numeric(df["bhk"], errors="coerce").astype("Int64")
    df["area_sqft"] = pd.to_numeric(df["area_sqft"], errors="coerce")
    df["total_price"] = pd.to_numeric(df["total_price"], errors="coerce")
    df = df.dropna(subset=["area_sqft", "total_price"]).query("area_sqft > 0 and total_price > 0")
    df["listed_date"] = pd.to_datetime(df["listed_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["listed_date"])  # remove rows with invalid dates

    rows = [
        (
            str(r.city), str(r.locality), str(r.property_type),
            (int(r.bhk) if pd.notna(r.bhk) else None),
            float(r.area_sqft), float(r.total_price), str(r.listed_date), str(r.source) if pd.notna(r.source) else None
        )
        for r in df.itertuples(index=False)
    ]
    return insert_listings(conn, rows)


def import_csv_from_url(conn, url: str) -> int:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    content = resp.content
    from io import BytesIO
    df = pd.read_csv(BytesIO(content))
    expected = [
        "city", "locality", "property_type", "bhk", "area_sqft", "total_price", "listed_date", "source"
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    df["bhk"] = pd.to_numeric(df["bhk"], errors="coerce").astype("Int64")
    df["area_sqft"] = pd.to_numeric(df["area_sqft"], errors="coerce")
    df["total_price"] = pd.to_numeric(df["total_price"], errors="coerce")
    df = df.dropna(subset=["area_sqft", "total_price"]).query("area_sqft > 0 and total_price > 0")
    df["listed_date"] = pd.to_datetime(df["listed_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["listed_date"])  # remove rows with invalid dates

    rows = [
        (
            str(r.city), str(r.locality), str(r.property_type),
            (int(r.bhk) if pd.notna(r.bhk) else None),
            float(r.area_sqft), float(r.total_price), str(r.listed_date), str(r.source) if pd.notna(r.source) else None
        )
        for r in df.itertuples(index=False)
    ]
    return insert_listings(conn, rows)


def query_dataframe(conn, sql: str, params: Tuple[Any, ...] = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def bootstrap():
    conn = connect()
    init_schema(conn)
    seed_cities_10(conn)
    return conn


def seed_synthetic_listings(conn, listings_per_city: int = 50, random_seed: int = 42) -> int:
    """Seed synthetic listings data across all cities if the table is empty.

    - Includes modern property types: Apartment, Penthouse, Studio, RK, Villa, Row House, Duplex, Triplex, Loft, Townhouse
    - Generates multiple localities per city: Central, East, West, North, South
    - Prices and areas are randomized with city-specific base factors for variety
    """
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM listing")
    if (cur.fetchone() or (0,))[0] > 0:
        return 0

    random.seed(random_seed)
    property_types = [
        "Apartment", "Penthouse", "Studio", "RK", "Villa", "Row House", "Duplex", "Triplex", "Loft", "Townhouse"
    ]
    locality_names = ["Central", "East", "West", "North", "South"]

    cur.execute("SELECT name FROM city ORDER BY name")
    cities = [r[0] for r in cur.fetchall()]
    today = datetime.today()

    rows: List[Tuple[str, str, str, Optional[int], float, float, str, Optional[str]]] = []
    for city in cities:
        # city factor to vary price levels
        base_factor = 1.0
        if city in {"Mumbai", "Navi Mumbai", "Delhi", "New Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"}:
            base_factor = 2.0
        elif city in {"Gurugram", "Noida", "Thane", "Jaipur", "Chandigarh", "Indore", "Surat", "Vadodara", "Kochi", "Coimbatore"}:
            base_factor = 1.5

        for _ in range(listings_per_city):
            locality = random.choice(locality_names)
            ptype = random.choice(property_types)
            # bhk: RK (0 or 1), Studio (0 or 1), otherwise 1-6
            if ptype in {"RK", "Studio", "Loft"}:
                bhk = random.choice([0, 1])
            elif ptype in {"Penthouse", "Villa", "Triplex"}:
                bhk = random.randint(3, 6)
            else:
                bhk = random.randint(1, 4)

            area = max(180.0, random.gauss(900.0, 350.0))
            if ptype in {"Penthouse", "Villa", "Row House", "Duplex", "Triplex"}:
                area *= random.uniform(1.4, 2.8)
            elif ptype in {"Studio", "RK", "Loft"}:
                area *= random.uniform(0.5, 0.9)

            # base ppsf in INR
            base_ppsf = random.uniform(2500, 12000) * base_factor
            ppsf = base_ppsf * random.uniform(0.8, 1.3)
            total_price = area * ppsf

            # random date within last 18 months (robust across year boundaries)
            month_offset = random.randint(0, 17)
            year = today.year
            month = today.month - month_offset
            while month <= 0:
                month += 12
                year -= 1
            day = random.randint(1, 28)
            ldate = f"{year:04d}-{month:02d}-{day:02d}"

            rows.append((city, locality, ptype, bhk, float(area), float(total_price), ldate, "synthetic"))

    return insert_listings(conn, rows)


def seed_city_synthetic(conn, city_name: str, listings: int = 150, random_seed: int = 123) -> int:
    """Seed synthetic listings for a specific city if it lacks listings."""
    cur = conn.cursor()
    # Check via join since we no longer maintain a view
    cur.execute(
        "SELECT COUNT(1) FROM listing l INNER JOIN city c ON c.id = l.city_id WHERE c.name = ?",
        (city_name,)
    )
    if (cur.fetchone() or (0,))[0] > 0:
        return 0
    random.seed(random_seed)
    property_types = [
        "Apartment", "Penthouse", "Studio", "RK", "Villa", "Row House", "Duplex", "Triplex", "Loft", "Townhouse"
    ]
    locality_names = ["Central", "East", "West", "North", "South"]
    today = datetime.today()
    rows: List[Tuple[str, str, str, Optional[int], float, float, str, Optional[str]]] = []
    base_factor = 2.0 if city_name in {"Mumbai", "Navi Mumbai", "Delhi", "New Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"} else 1.3
    for _ in range(listings):
        locality = random.choice(locality_names)
        ptype = random.choice(property_types)
        if ptype in {"RK", "Studio", "Loft"}:
            bhk = random.choice([0, 1])
        elif ptype in {"Penthouse", "Villa", "Triplex"}:
            bhk = random.randint(3, 6)
        else:
            bhk = random.randint(1, 4)
        area = max(180.0, random.gauss(950.0, 380.0))
        if ptype in {"Penthouse", "Villa", "Row House", "Duplex", "Triplex"}:
            area *= random.uniform(1.4, 2.8)
        elif ptype in {"Studio", "RK", "Loft"}:
            area *= random.uniform(0.5, 0.9)
        base_ppsf = random.uniform(3000, 14000) * base_factor
        ppsf = base_ppsf * random.uniform(0.8, 1.3)
        total_price = area * ppsf
        month_offset = random.randint(0, 17)
        year = today.year
        month = today.month - month_offset
        while month <= 0:
            month += 12
            year -= 1
        day = random.randint(1, 28)
        ldate = f"{year:04d}-{month:02d}-{day:02d}"
        rows.append((city_name, locality, ptype, bhk, float(area), float(total_price), ldate, "synthetic"))
    return insert_listings(conn, rows)


def seed_missing_cities_listings(conn, listings_per_city: int = 80) -> int:
    """Ensure each city has at least some listings by seeding those with zero."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM city")
    cities = [r[0] for r in cur.fetchall()]
    total = 0
    for cname in cities:
        cur.execute(
            "SELECT COUNT(1) FROM listing l INNER JOIN city c ON c.id = l.city_id WHERE c.name = ?",
            (cname,)
        )
        if (cur.fetchone() or (0,))[0] == 0:
            total += seed_city_synthetic(conn, cname, listings=listings_per_city)
    return total


