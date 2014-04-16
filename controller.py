"""
module for control server processes
"""
import time
from datetime import datetime
import beerery.sensors.TempSensors as TempSensors
import beerery.loggers as loggers
import beerery.pid as PID
import beerery.constants as constants
import beerery.fileio as fileio
from pprint import pprint
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import RPIO  # only available on the raspberry pi, pylint: disable=F0401

DEV_LOGGING = False


def log(message):
    """log a dev debug message"""
    if DEV_LOGGING:
        pprint(message)


class Input(object):

    """
    Class representing an input sensor
    """

    def __init__(self, name, input_object, units, adjustment):
        self.name = name
        self.input_impl = input_object
        self.last_value = 0
        self.units = units
        self.adjustment = adjustment

    def calculate(self):
        """
        retrieve sensor value
        """
        self.last_value = self.input_impl.get_temp()

        if self.adjustment:
            self.last_value += self.adjustment

        input_state = {
            "name": self.name,
            "value": self.last_value,
            "units": self.units,
            "date_servertime": datetime.now().strftime(constants.DATE_FORMAT),
            "date_utc": datetime.utcnow().strftime(
            constants.DATE_FORMAT)
        }

        fileio.log_input_state(self.name, input_state)

        return input_state


class Output(object):

    """
    Class representing an output pin
    """

    def __init__(self, output_handler, **kwargs):
        self.name = kwargs["name"]
        self.controller = output_handler
        self.input = kwargs["input"]
        self.mode = kwargs["mode"]
        self.pin = kwargs["pin"]
        self.active = kwargs["active"]

    def signal_pin_for_ms(self, millis):
        """
        signal the gpio pin for a given time
        """
        # set the pin high
        RPIO.output(self.pin, True)

        # sleep
        time.sleep(millis / 1000)

        # set it back low
        if RPIO.gpio_function(self.pin) == RPIO.OUT:
            RPIO.output(self.pin, False)

    def set_pin_for_ms(self, millis):
        """
        schedule a thread to signal the pin.
        I think this needs refactoring to use a single thread for all
        the signalling
        """
        thread = Thread(target=self.signal_pin_for_ms, args=[millis])
        thread.start()

    def calculate(self, input_object, input_value, period_ms):
        """
        calculate and set output pin if required
        """
        self.controller.input = input_value
        value_computed = self.controller.compute()

        if self.controller.output == None or value_computed == False:
            return  # nothing to do with this controller

        if self.mode == constants.TPC_OUTPUT:
            self.set_pin_for_ms(
                self.controller.output / 100 * period_ms)
        elif self.mode == constants.PWM_OUTPUT:
            # not yet implemented, tpc is probably adequate
            pass

        # write output values to state files
        output_state = {
            "name": self.name,
            "mode": self.mode,
            "output_value": self.controller.output,
            "input_value": self.controller.input,
            "input_name": input_object.name,
            "date_servertime": datetime.now().strftime(constants.DATE_FORMAT),
            "date_utc": datetime.utcnow().strftime(constants.DATE_FORMAT)
        }

        fileio.log_output_state(self.name, output_state)


class ConfigFileWatcher(FileSystemEventHandler):

    """
    File watcher for watching config file changes
    """

    def __init__(self, controller):
        self.controller = controller

    def on_any_event(self, event):
        self.controller.on_config_file_event()


class Controller(object):

    """
    Controller class
    """

    def __init__(self):
        self.controller_config = {}
        self.controller_config["app_params_current"] = False
        self.controller_config["config_file_observer"] = None

        self.inputs = {}
        self.outputs = {}
        self.logs = []
        self.programs = {}

    def on_config_file_event(self):
        """called when a chnage occurs to any of the config files"""
        self.controller_config["app_params_current"] = False

    def connect_logs(self):
        """read the log config and create associated log objects"""
        logs = []

        if not self.controller_config["logging_enabled"]:
            return logs

        for log_config in self.controller_config["logs"]:
            logger = None
            log_type = log_config["type"]
            if log_type == constants.MONGODB_LOG:
                logger = loggers.MongoDBLogger(
                    log_config["db_uri"], log_config["database"])
            else:
                raise Exception("Unknown log type '{}'".format(log_type))

            logs.append(logger)

        return logs

    def connect_inputs(self):
        """
        read the input config and create associated input reading objects
        """
        input_dict = {}

        for input_config in self.controller_config["inputs"]:
            if input_config["active"] != True:
                continue

            input_handler = None
            input_type = input_config["type"]
            if input_type == constants.THERMISTOR_INPUT_TYPE:
                input_handler = TempSensors.ThermistorSensor(
                    input_config["adc_channel"])
            elif input_type == constants.ONEWIRE_TEMP_INPUT_TYPE:
                input_handler = TempSensors.OneWireTempSensor(
                    input_config["address"])
            elif input_type == constants.TMP36_TEMP_INPUT_TYPE:
                input_handler = TempSensors.TMP36TempSensor(
                    input_config["adc_channel"])
            else:
                raise Exception("Unknown input type '{}'".format(input_type))

            adjustment = None
            if "adjustment" in input_config:
                adjustment = input_config["adjustment"]

            io_input = Input(
                input_config["name"], input_handler, input_handler.units(),
                adjustment)

            input_dict[input_config["name"]] = io_input

        return input_dict

    def connect_outputs(self):
        """
        read the output config and create associated output pin control objects
        """
        output_dict = {}

        for output_config in self.controller_config["outputs"]:
            if output_config["active"] != True:
                continue

            log("output: {}".format(output_config["name"]))
            output_handler = None
            output_type = output_config["type"]
            output_type_controller = output_type["controller"]
            if output_type_controller == constants.PID_OUTPUT_CONTROLLER_TYPE:
                output_handler = PID.PidController(
                    sample_time_ms=self.controller_config[
                        "control_sample_time_ms"],
                    **output_type["config"])

                if output_config["mode"] == constants.TPC_OUTPUT:
                    output_handler.set_output_limits(0, 100)
                elif output_config["mode"] == constants.PWM_OUTPUT:
                    output_handler.set_output_limits(0, 100)
            else:
                raise Exception("Unknown output type '{}'".format(output_type))

            # setup the gpio pin
            RPIO.setup(output_config["pin"], RPIO.OUT, initial=RPIO.LOW)

            # I think ** makes sense here and simplifies the code a lot.
            # pylint: disable=W0142
            io_output = Output(output_handler, **output_config)

            output_dict[output_config["name"]] = io_output

        return output_dict

    def connect_programs(self):
        """
        read the program config and create associated program objects if needed
        """
        program_dict = {}

        return program_dict

    def read_app_params(self):
        """
        load and read all the app configuration
        """
        if self.controller_config["app_params_current"] == True:
            return False

        config_file_observer = self.controller_config["config_file_observer"]
        if config_file_observer:
            config_file_observer.stop()

        config_file_observer = Observer()
        file_change_handler = ConfigFileWatcher(self)

        # load the controller config
        self.controller_config.update(fileio.load_config_from_json_file(
            "config/controller.json"))

        # load the inputs config
        self.controller_config["inputs"] = fileio.load_config_from_json_file(
            "config/inputs.json")

        # load the outputs
        self.controller_config["outputs"] = fileio.load_config_from_json_file(
            "config/outputs.json")

        # load log configs
        self.controller_config["logs"] = fileio.load_config_from_json_file(
            "config/logs.json")

        # load programs
        self.controller_config["programs"] = fileio.load_config_from_json_file(
            "config/programs.json")

        config_file_observer.schedule(
            file_change_handler, "config", recursive=False)
        config_file_observer.start()

        self.controller_config["config_file_observer"] = config_file_observer
        self.controller_config["file_change_handler"] = file_change_handler
        self.controller_config["app_params_current"] = True

        return True

    def evaluate_programs(self):
        """
        reload config and build objects if needed
        """

    def load_config_if_needed(self):
        """
        reload config and build objects if needed
        """
        if self.read_app_params():

            self.inputs = self.connect_inputs()
            self.outputs = self.connect_outputs()
            self.logs = self.connect_logs()

    def control(self, loop_callback=None):
        """
        main control loop method for the controller class
        """
        # do any onetime setup

        try:
            while True:
                # evaluate any active programs
                self.evaluate_programs()

                # reload app config if neede
                self.load_config_if_needed()

                sample_ms = self.controller_config["control_sample_time_ms"]

                # process the inputs
                input_objects = self.inputs.values()

                for input_object in input_objects:
                    input_state = input_object.calculate()

                    for logger in self.logs:
                        logger.log_input(input_object.name, input_state)

                # process outputs
                output_objects = self.outputs.values()

                for output in output_objects:
                    input_for_output = self.inputs[output.input]

                    if input_for_output != None:
                        input_value = input_for_output.last_value

                        output_state = output.calculate(input_for_output,
                                                        input_value,
                                                        sample_ms)

                        for logger in self.logs:
                            logger.log_output(output.name, output_state)

                if loop_callback != None:
                    loop_callback()

                # TODO: keep track of how long the above takes and subtract that
                # from the sleep time
                time.sleep(sample_ms / 1000.0)
        finally:
            RPIO.cleanup()

            self.controller_config["app_params_current"] = False
            if self.controller_config["config_file_observer"]:
                self.controller_config["config_file_observer"].stop()
