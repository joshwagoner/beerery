from pymongo import MongoClient

class Logger(object):
  def log_input(self, name, info_dict):
    pass

  def log_output(self, name, info_dict):
    pass

class JsonFileLogger(Logger):
  def __init__(self, file):
    pass
  
  def log_input(self, name, info_dict):
    pass

  def log_output(self, name, info_dict):
    pass

class MongoDBLogger(Logger):
  def __init__(self, db_uri, database):
    self.client = MongoClient(db_uri)
    self.db = self.client[database]
  
  def log_input(self, name, info_dict):
    input_collection = self.db["input_{}".format(name)]
    input_collection.insert(info_dict)

  def log_output(self, name, info_dict):
    output_collection = self.db["output_{}".format(name)]
    output_collection.insert(info_dict)
    