# This is a script for saving google-analytics-related csv files as MySQL database tables
# For example, there may be a region_age.csv
# It goes to the table region_age

import csv
import MySQLdb
from sys import argv

mydb = MySQLdb.connect(host='localhost',
  user='root',
  passwd='root',
  db='data')
cursor=mydb.cursor()

csv_data = csv.reader(file(argv[1], 'rU'))
headers = ["".join(entry.split()) for entry in csv_data.next()]
table_name=argv[1][:argv[1].find('.')]

# We assume that the first column is something like 'san-francisco-california', city-region from Google Analytics
headers[0]='ID1'
create_table_query = "CREATE TABLE IF NOT EXISTS %s (%s);" % (table_name, ','.join(["%s VARCHAR(100)" % headers[0]] + ["%s DOUBLE" % h for h in headers[1:]]))

cursor.execute(create_table_query)

for r in csv_data:
  insert_query = "INSERT INTO %s(%s) VALUES(%s)" % (table_name, ','.join(headers), ','.join(['"%s"' % x for x in r]))
  cursor.execute(insert_query)

mydb.commit()
cursor.close()


#"INSERT INTO %s(%s) VALUES(%s)" % (table_name, ','.join(headers[1:]), ','.join(["'"+str(r[0])+"'"]+[str(x) for x in r[1:]]
