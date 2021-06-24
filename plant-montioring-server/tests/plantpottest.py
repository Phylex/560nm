import PlantPot as ppt
import time
import sys
import datetime as dt
db_path = sys.argv[1]
schema_path = sys.argv[2]
ppt.setup_database(db_path, schema_path)
pm = ppt.PlantManager(db_path, 10)

duration=dt.timedelta(days=0, hours=0, weeks=0, years=0, minutes=5)
t = dt.datetime.now()
now = dt.datetime.now()
while now - t < duration:
    print(now - t)
    now = dt.datetime.now()
    pm.measure_all_pots()
    time.sleep(5)
