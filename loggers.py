"""
module containing classes related to logging beerery data
"""
from pymongo import MongoClient


class Logger(object):

    """
    base class for loggers
    """

    def log_input(self, name, info_dict):
        """
        log an input value
        """
        pass

    def log_output(self, name, info_dict):
        """
        log an output value
        """
        pass


class JsonFileLogger(Logger):

    """
    logger that will eventually write to a local file
    """

    def __init__(self, file_path):
        pass

    def log_input(self, name, info_dict):
        pass

    def log_output(self, name, info_dict):
        pass


class MongoDBLogger(Logger):

    """
    Logger that writes to a mongo db database
    """

    def __init__(self, db_uri, database):
        self.client = MongoClient(db_uri)
        self.database = self.client[database]

    def log_input(self, name, info_dict):
        input_collection = self.database["input_{}".format(name)]
        input_collection.insert(info_dict)

    def log_output(self, name, info_dict):
        output_collection = self.database["output_{}".format(name)]
        output_collection.insert(info_dict)
