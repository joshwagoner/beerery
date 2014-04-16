"""
module for reading and writing app config
"""
import json


def load_config_from_json_file(file_path):
    """
    loads config from one of the json config files
    """

    dict_from_json = None
    with open(file_path) as input_json:
        dict_from_json = json.load(input_json)

    return dict_from_json


def write_state(file_path, state):
    """ write json to a file """
    # write input values to state files
    #
    # TODO: maybe make this async via pushing onto
    # separate thread, eventually.
    # should probably also write to a temp file
    # and then atomically move to "current" file
    with open(file_path, 'w+') as outfile:
        json.dump(state, outfile)


def log_input_state(name, state):
    """
    log input state to file
    """
    write_state("state/input_{}.json".format(name), state)


def log_output_state(name, state):
    """
    log input state to file
    """
    write_state("state/output_{}.json".format(name), state)
