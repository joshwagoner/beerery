"""
module for control server processes

need to convert this to a class?
"""
import time
from datetime import datetime
import beerery.sensors.TempSensors as TempSensors
import beerery.loggers as loggers
import beerery.pid as PID
import json
from pprint import pprint
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import RPIO  # only available on the raspberry pi, pylint: disable=F0401

THERMISTOR_INPUT_TYPE = "thermistor"
ONEWIRE_TEMP_INPUT_TYPE = "DS18B20"
TMP36_TEMP_INPUT_TYPE = "TMP36"
PID_OUTPUT_CONTROLLER_TYPE = "PID"
TIME_PROPORTIONAL_CONTROL_OUTPUT = "TPC"
PULSE_WIDTH_MODULATION_OUTPUT = "PWM"
MONGODB_LOG = "mongodb"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

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

    def log_state(self, input_state):
        """
        log input state to file
        """
        # write input values to state files
        #
        # TODO: maybe make this async via pushing onto
        # separate thread, eventually.
        # should probably also write to a temp file
        # and then atomically move to "current" file
        file_path = "state/input_{}.json".format(self.name)
        with open(file_path, 'w+') as outfile:
            json.dump(input_state, outfile)

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
            "date_servertime": datetime.now().strftime(DATE_FORMAT),
            "date_utc": datetime.utcnow().strftime(
            DATE_FORMAT)
        }

        self.log_state(input_state)

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

        if self.mode == TIME_PROPORTIONAL_CONTROL_OUTPUT:
            self.set_pin_for_ms(
                self.controller.output / 100 * period_ms)
        elif self.mode == PULSE_WIDTH_MODULATION_OUTPUT:
            # not yet implemented, tpc is probably adequate
            pass

        # write output values to state files
        # maybe make this async?
        output_state = {
            "name": self.name,
            "mode": self.mode,
            "output_value": self.controller.output,
            "input_value": self.controller.input,
            "input_name": input_object.name,
            "date_servertime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open("state/output_{}.json".format(self.name), 'w+') as outfile:
            json.dump(output_state, outfile)


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
        self.app_params = {}
        self.app_params_current = False
        self.config_file_observer = None
        self.file_change_handler = None

        self.inputs = {}
        self.outputs = {}
        self.logs = []

    def on_config_file_event(self):
        """called when a chnage occurs to any of the config files"""
        self.app_params_current = False

    def connect_logs(self):
        """read the log config and create associated log objects"""
        logs = []

        if not self.app_params["logging_enabled"]:
            return logs

        for log_config in self.app_params["logs"]:
            logger = None
            log_type = log_config["type"]
            if log_type == MONGODB_LOG:
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

        for input_config in self.app_params["inputs"]:
            if input_config["active"] != True:
                continue

            input_handler = None
            input_type = input_config["type"]
            if input_type == THERMISTOR_INPUT_TYPE:
                input_handler = TempSensors.ThermistorSensor(
                    input_config["adc_channel"])
            elif input_type == ONEWIRE_TEMP_INPUT_TYPE:
                input_handler = TempSensors.OneWireTempSensor(
                    input_config["address"])
            elif input_type == TMP36_TEMP_INPUT_TYPE:
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

        for output_config in self.app_params["outputs"]:
            if output_config["active"] != True:
                continue

            log("output: {}".format(output_config["name"]))
            output_handler = None
            output_type = output_config["type"]
            output_type_controller = output_type["controller"]
            if output_type_controller == PID_OUTPUT_CONTROLLER_TYPE:
                output_handler = PID.PidController(
                    sample_time_ms=self.app_params["control_sample_time_ms"],
                    **output_type["config"])

                if output_config["mode"] == TIME_PROPORTIONAL_CONTROL_OUTPUT:
                    output_handler.set_output_limits(
                        0, 100)  # self.app_params["control_sample_time_ms"])
                elif output_config["mode"] == PULSE_WIDTH_MODULATION_OUTPUT:
                    output_handler.set_output_limits(0, 100)
            else:
                raise Exception("Unknown output type '{}'".format(output_type))

            # setup the gpio pin
            RPIO.setup(output_config["pin"], RPIO.OUT, initial=RPIO.LOW)

            # I think ** makes sense here. pylint: disable=W0142
            io_output = Output(output_handler, **output_config)

            output_dict[output_config["name"]] = io_output

        return output_dict

    def load_param_from_json_file(self, config_name, file_path, log_name):
        """
        loads parameters from one of the json config files
        """
        log("loading {}...".format(log_name))

        input_json = open(file_path)
        dict_from_json = json.load(input_json)
        if config_name:
            self.app_params[config_name] = dict_from_json
        input_json.close()

        log("{} loaded.".format(log_name))
        log(" data:")
        log(dict_from_json)

        return dict_from_json

    def read_app_params(self):
        """
        load and read all the app configuration
        """
        if self.app_params_current == True:
            return False

        if self.config_file_observer:
            self.config_file_observer.stop()

        self.config_file_observer = Observer()
        self.file_change_handler = ConfigFileWatcher(self)

        controller_config = self.load_param_from_json_file(
            None, "config/controller.json", "controller config")
        self.app_params.update(controller_config)

        # load the inputs config
        self.load_param_from_json_file(
            "inputs", "config/inputs.json", "inputs")

        # load the outputs
        self.load_param_from_json_file(
            "outputs", "config/outputs.json", "outputs")

        # load log configs
        self.load_param_from_json_file("logs", "config/logs.json", "logs")

        self.config_file_observer.schedule(
            self.file_change_handler, "config", recursive=False)
        self.config_file_observer.start()

        self.app_params_current = True

        return True

    def load_app_params_if_needed(self):
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
                self.load_app_params_if_needed()

                sample_ms = self.app_params["control_sample_time_ms"]

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

            self.app_params_current = False
            self.config_file_observer.stop()
