import sqlite3

con1 = sqlite3.connect("../pixous_staging.db")
cur1 = con1.cursor()

# Fix the broken client name
cur1.execute("UPDATE clients SET company_name = 'Pixous Technologies', billing_address = '123 Main St, Bangalore, India', gstin = '29ABCDE1234F1Z5' WHERE company_name = 'Internal Server Error'")
con1.commit()

print("Fixed client info")
con1.close()
