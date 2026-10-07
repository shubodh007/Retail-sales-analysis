import psycopg2

c = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", dbname="retail_intelligence")
cur = c.cursor()
cur.execute("SELECT dim_key, count(*), max(abs(deviation)) FROM anomalies WHERE dataset_id='d0793ce2-624c-465d-88ab-cb8018a2c489' AND dimension='product' GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT date, observed, expected, deviation FROM anomalies WHERE dataset_id='d0793ce2-624c-465d-88ab-cb8018a2c489' AND dimension='global' ORDER BY date")
print("GLOBAL:")
for r in cur.fetchall():
    print(r)
c.close()
