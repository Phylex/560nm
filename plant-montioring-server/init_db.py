from sqlalchemy import create_engine, MetaData
from JMS_server.settings import config
from JMS_server.db import plant, measurement
from datetime import datetime

DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"

def create_table(engine):
    meta = MetaData()
    meta.create_all(bind=engine, tables=[plant, measurement])

def sample_data(engine):
    conn = engine.connect()
    conn.execute(plant.insert(), [
        {'id': 0, 'address': 0,
         'species': 'test species'},
        {'id': 1, 'address': 1,
         'species': 'other species'},
    ])
    conn.execute(measurement.insert(), [
        {'plant_id': 0, 'timestamp': datetime(2021, 1, 1, 0, 0, 0),
         'moisture': 0, 'brightness': 0},
        {'plant_id': 0, 'timestamp': datetime(2021, 1, 1, 0, 0, 5),
         'moisture': 1, 'brightness': 1},
        {'plant_id': 0, 'timestamp': datetime(2021, 1, 1, 0, 0, 10),
         'moisture': 2, 'brightness': 2},
        {'plant_id': 0, 'timestamp': datetime(2021, 1, 1, 0, 0, 15),
         'moisture': 3, 'brightness': 3},
        {'plant_id': 1, 'timestamp': datetime(2021, 1, 1, 0, 0, 0),
         'moisture': 0, 'brightness': 0},
        {'plant_id': 1, 'timestamp': datetime(2021, 1, 1, 0, 0, 5),
         'moisture': 1, 'brightness': 1},
        {'plant_id': 1, 'timestamp': datetime(2021, 1, 1, 0, 0, 10),
         'moisture': 2, 'brightness': 2},
        {'plant_id': 1, 'timestamp': datetime(2021, 1, 1, 0, 0, 15),
         'moisture': 3, 'brightness': 3}
    ])
    conn.close()

if __name__ == '__main__':
    db_url = DSN.format(**config['postgres'])
    engine = create_engine(db_url)
    create_table(engine)
    sample_data(engine)
