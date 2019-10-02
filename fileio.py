"""
module for reading and writing app config
"""
import json
import sys
import os

sys.modules[__name__].base_dir = ""


def set_base_directory(path):
    """
    sets the base directory used for beerery fileio ops
    """
    sys.modules[__name__].base_dir = path


def full_fileio_path(path):
    """
    gets the full path to the path passed in
    """
    directory = sys.modules[__name__].base_dir

    return os.path.join(directory, path)


def load_config_from_json_file(file_path):
    """
    loads config from one of the json config files
    """
    dict_from_json = None

    full_path = full_fileio_path(file_path)
    with open(full_path) as input_json:
        dict_from_json = json.load(input_json)

    return dict_from_json


def save_output_config(output_config):
    """saves an output config file"""
    write_json(full_fileio_path("config/outputs.json"), output_config)


def write_json(file_path, object_to_write):
    """ write json to a file """
    # write input values to state files
    #
    # TODO: maybe make this async via pushing onto
    # separate thread, eventually.
    # should probably also write to a temp file
    # and then atomically move to "current" file
    with open(file_path, 'w+') as outfile:
        json.dump(object_to_write, outfile)


def log_input_state(name, state):
    """
    log input state to file
    """
    write_json(full_fileio_path("state/input_{}.json".format(name)), state)


def log_output_state(name, state):
    """
    log input state to file
    """
    write_json(full_fileio_path("state/output_{}.json".format(name)), state)


def log_program_state(name, state):
    """
    log input state to file
    """
    write_json(full_fileio_path("state/program_{}.json".format(name)), state)
