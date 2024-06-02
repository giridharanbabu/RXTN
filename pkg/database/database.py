from pymongo import MongoClient


class Database:
    def __init__(self, mongo_uri, db_name):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

    def get_collection(self, collection_name):
        return self.db[collection_name]

    def check_connection(self):
        try:
            self.client.server_info()  # Check if the server is available
            return True
        except Exception as e:
            return False

    def collection_exists(self, collection_name):
        return collection_name in self.db.list_collection_names()


MONGO_URI = ("mongodb+srv://giri1208srinivas:mongouser@cluster0.extptud.mongodb.net/?retryWrites=true&w=majority"
             "&appName=Cluster0")
DB_NAME = 'rxtn'

database = Database(MONGO_URI, DB_NAME)
user_collection = database.get_collection('users')

print(database)
