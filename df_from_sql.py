import pandas as pd
from django.db import connection

def load_all_tables_as_df():
  cursor=connection.cursor()
  cursor.execute("SHOW TABLES LIKE 'region%'")
  region_tables=cursor.fetchall()
  
  result={}
  for table in region_tables: 
    print 'processing '+table[0]
    cursor.execute("SHOW COLUMNS FROM %s" % table)
    cols = cursor.fetchall()

    cursor.execute("SELECT * FROM %s" % table)
    rows=cursor.fetchall()

    df=pd.DataFrame([x[1:] for x in rows],  index=[x[0] for x in rows], columns=[x[0] for x in cols[1:]])
    result[table[0]]=df
  return result
