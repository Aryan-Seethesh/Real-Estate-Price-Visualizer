🏠 Real Estate Price Visualizer

A Python-based desktop application that analyzes and visualizes real estate prices across multiple cities, enabling users to compare property prices efficiently using interactive filters and charts.

📌 Features

Analyzes thousands of real estate listings across cities and localities

Interactive filters for:

City

Locality

Property type / BHK

Price range and area

Computes key metrics such as median price per square foot (PPSF)

Dynamic visualizations including price distributions and comparisons

Clean, responsive GUI built using PySide6 (Qt)

🧠 System Design

Uses a relational SQLite database with normalized tables (cities, localities, listings)

Data is ingested from CSV files and processed using Python

SQL queries and joins are used to derive insights efficiently

Outliers are handled to improve data quality and accuracy

⚙️ Tech Stack

Language: Python

Database: SQLite

GUI Framework: PySide6 (Qt)

Visualization: Matplotlib

Libraries: Pandas, NumPy

🚀 Performance & Scale

Cleaned and analyzed 10,000+ real estate listings

Enables fast price comparison through optimized queries and filtering

Designed for scalability and easy dataset expansion

📂 Project Structure
.
├── qt_app.py          # GUI and visualization logic
├── db.py              # Database schema and queries
├── utils.py           # Data cleaning and preprocessing
├── real_estate.db     # SQLite database
├── listings_sample.csv
├── requirements.txt

▶️ How to Run

Install dependencies:

pip install -r requirements.txt


Run the application:

python qt_app.py

🎯 Learning Outcomes

Hands-on experience with data cleaning and preprocessing

Designing and querying relational databases

Building interactive data-driven GUIs

Applying Python and SQL to solve real-world problems

📌 Future Enhancements

Add price trend analysis over time

Support for additional cities and larger datasets

Export insights as reports or CSV files
