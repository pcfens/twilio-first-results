from local_settings import *
from first_results import first_results

data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
data.fetch_all_data()
