"""
programs for running the controllers
"""
import beerery.fileio as fileio
from pprint import pprint


class Program(object):

    """
    class representing a program to be run by the controller.
    programs are configured in config/programs.json.
    """

    def __init__(self, program_config):
        super(Program, self).__init__()
        self.name = program_config["name"]
        self.config = program_config
        self.steps = []

        self.initialize_steps()

    def initialize_steps(self):
        """
        creates the step objects from the config
        """
        for step_config in self.config["steps"]:
            step = ProgramStep(self, step_config)
            self.steps.append(step)

    def run(self):
        """
        calculate any changes needed based on the time.
        returns True if an input or output change resulted
        """
        # action = self.steps[0].actions[0]
        # action.apply()
        # for step in self.steps:
        #     for action in step.actions:
        #         action.apply()

    def start(self):
        """activate the program and start running it"""


class ProgramStep(object):

    def __init__(self, program, step_config):
        super(ProgramStep, self).__init__()
        self.name = step_config["name"]
        self.config = step_config
        self.program = program
        self.actions = []

        self.initialize_actions()

    def initialize_actions(self):
        """
        creates the action objects from the config
        """
        for action_config in self.config["actions"]:
            if "action" in action_config:
                pass  # don't do anything yet
            elif "type" in action_config:
                action_type = action_config["type"]

                if action_type == "PID":
                    step = PIDAction(self.program, action_config)
                    self.actions.append(step)


class ProgramAction(object):

    """docstring for ProgramAction"""

    def __init__(self, program, action_config):
        super(ProgramAction, self).__init__()
        self.type = action_config["type"]
        self.program = program
        self.output_config = None
        self.output_dict = None
        self.output_name = action_config["output_name"]

    def apply(self):
        """
        apply the step to the output config files as needed
        """
        pass

    def could_be_active(self):
        """
        determine if this action could be active given
        current state of the system
        """
        pass

    def read_output_config(self):
        """
        reads the outputs config json file and returns the dict
        for the output associated with this action
        """
        if self.output_dict:
            return self.output_dict

        self.output_config = fileio.load_config_from_json_file(
            "config/outputs.json")
        output = [
            o for o in self.output_config if o["name"] == self.output_name]
        if not output or output.count == 0:
            raise Exception(
                "Output '{}' not found. program: {}".format(self.output_name,
                                                            self.program.name))

        self.output_dict = output[0]
        return self.output_dict


class BasicAction(ProgramAction):

    """
    Program action for basic actions like 'alarm', 'wait', etc.
    """

    def __init__(self, program, action_config):
        super(BasicAction, self).__init__(program, action_config)
        self.config_changed = False


class PIDAction(ProgramAction):

    """
    an action that controls a PID output
    """

    def __init__(self, program, action_config):
        super(PIDAction, self).__init__(program, action_config)
        self.output = action_config.get("output")
        self.setpoint = action_config.get("setpoint")
        self.config_changed = False

    def validate_config(self, set_active):
        """
        validates that the output config to write to has the proper settings
        """
        output = self.read_output_config()
        if not output:
            raise Exception(
                "Output '{}' not found. program: {}".format(self.output_name,
                                                            self.program.name))

        correct_conf = "controller" in output["type"]
        correct_conf = correct_conf and output["type"]["controller"] == "PID"
        if not correct_conf:
            raise Exception(
                "'{}' must be type PID. program: {}".format(self.output_name,
                                                            self.program.name))

        output_type = output["type"]
        correct_conf = "config" in output_type
        if correct_conf:
            type_config = output_type["config"]
            correct_conf = "set_point" in type_config and "mode" in type_config

        if not correct_conf:
            err_msg = "'{}' must have correct config key. program: {}"
            raise Exception(err_msg.format(self.output_name,
                                           self.program.name))

        if output["active"] != set_active:
            output["active"] = set_active
            self.config_changed = True

        return type_config

    def apply(self):
        self.config_changed = False

        config = self.validate_config(True)

        if self.output == "PID":
            if config["mode"] != 1 or config["set_point"] != self.setpoint:
                self.config_changed = True
                config["mode"] = 1
                config["set_point"] = self.setpoint
        else:
            if config["mode"] != 0 or config["output"] != self.output:
                self.config_changed = True
                config["mode"] = 0
                config["output"] = self.output

        if self.config_changed:
            fileio.save_output_config(self.output_config)
