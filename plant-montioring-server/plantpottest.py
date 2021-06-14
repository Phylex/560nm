import PlantPot as ppt
import sys
db_path = sys.argv[1]
schema_path = sys.argv[2]
ppt.setup_database(db_path, schema_path)
pm = ppt.PlantManager(db_path, 10)
