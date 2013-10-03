import pymongo
db = pymongo.Connection('localhost')['skyline-dev']

# check whether script has already run by looking for a document that should
# not exist until it has
if db.ratestructure.find_one({'_id': {'account': '10001', 'sequence': 1,
        'version': 0, 'type': 'CPRS'}}) != None:
    raise ValueError('This script was already run!')

initial_count = db.ratestructure.count();
docs = [
    {'_id': {'account': '10001', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 10,'version': 0,  'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 11,'version': 0,  'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 12,'version': 0,  'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 13,'version': 0,  'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 14,'version': 0,  'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 4, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 5, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 6, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 7, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 8, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10001', 'sequence': 9, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': 'washgas', 'rate_structure_name': 'COMMERCIAL_HEAT-COOL'},
    {'_id': {'account': '10002', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 4, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 5, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 6, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 7, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 8, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 9, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': '101 - Residential Service'},
    {'_id': {'account': '10002', 'sequence': 10,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 11,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 12,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 13,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 14,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 15,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 16,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 17,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 18,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10002', 'sequence': 19,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10003', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10003', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10003', 'sequence': 10,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 11,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 12,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 13,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 14,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 15,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 4, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 5, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 6, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 7, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10003', 'sequence': 8, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 10,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 11,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 12,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 13,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 14,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 16,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 3, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 4, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 7, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 8, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10004', 'sequence': 9, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10005', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10005', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10005', 'sequence': 4, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Heat'},
    {'_id': {'account': '10005', 'sequence': 5, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Non Heat'},
    {'_id': {'account': '10005', 'sequence': 10,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 11,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 12,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 13,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 14,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 15,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 16,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 18,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 6, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 7, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 8, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10005', 'sequence': 9, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10007', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Non Heat'},
    {'_id': {'account': '10007', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Non Heat'},
    {'_id': {'account': '10007', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': 'DC Non Residential Non Heat'},
    {'_id': {'account': '10008', 'sequence': 1, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 10,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 12,'version': 0,  'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 2, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 3, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 4, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 6, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 7, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 8, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10008', 'sequence': 9, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 4, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 5, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 7, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10009', 'sequence': 8, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10011', 'sequence': 1, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10011', 'sequence': 2, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10011', 'sequence': 3, 'version': 0, 'type': 'CPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10012', 'sequence': 1, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10012', 'sequence': 2, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10012', 'sequence': 5, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10013', 'sequence': 2, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10013', 'sequence': 3, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10014', 'sequence': 1, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10014', 'sequence': 2, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10016', 'sequence': 1, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10018', 'sequence': 3, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
    {'_id': {'account': '10019', 'sequence': 2, 'version': 0, 'type': 'UPRS'}, 'rates': [], 'utility_name': '', 'rate_structure_name': ''},
]

# "insert" is used to ensure that documents don't already exist
for doc in docs:
    db.ratestructure.insert(doc)

# check for success
final_count = db.ratestructure.count()
assert final_count - initial_count == len(docs)
