import sqlite3
conn = sqlite3.connect('pixous_staging.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]
print(f"V1 tables: {tables}")

conn2 = sqlite3.connect('../pixous_staging.db')
c2 = conn2.cursor()
c2.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables2 = [row[0] for row in c2.fetchall()]
print(f"V2 tables: {tables2}")

print(f"Number of estimations in V1:")
c.execute("SELECT COUNT(*) FROM estimation")
print(c.fetchone()[0])
