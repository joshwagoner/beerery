"""
module for control server processes
"""
import time
from datetime import datetime
import beerery.sensors.tempsensors as tempsensors
import beerery.loggers as loggers
import beerery.pid as PID
import beerery.constants as constants
import beerery.fileio as fileio
import beerery.program as program
from pprint import pprint
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import RPIO  # only available on the raspberry pi, pylint: disable=F0401

DEV_LOGGING = True


def log(message):
    """log a dev debug message"""
    if DEV_LOGGING:
        pprint(message)


def millis():
    """returns current time as milliseconds"""
    return int(round(time.time() * 1000))


class Input(object):

    """
    Class representing an input sensor
    """

    def __init__(self, name, adjustment):
        self.name = name
        self.input_impl = None
        self.last_value = 0
        self.adjustment = adjustment

    def set_type(self, input_type, input_config):
        """
        create the proper handler/reader for retrieving the input values
        """
        if input_type == constants.THERMISTOR_INPUT_TYPE:
            input_handler = tempsensors.ThermistorSensor(
                input_config["adc_channel"])
        elif input_type == constants.ONEWIRE_TEMP_INPUT_TYPE:
            input_handler = tempsensors.OneWireTempSensor(
                input_config["address"])
        elif input_type == constants.TMP36_TEMP_INPUT_TYPE:
            input_handler = tempsensors.TMP36TempSensor(
                input_config["adc_channel"])
        else:
            raise Exception("Unknown input type '{}'".format(input_type))

        self.input_impl = input_handler

    def calculate(self, callback=None):
        """
        retrieve sensor value
        """
        self.last_value = self.input_impl.get_temp()

        if self.adjustment:
            self.last_value += self.adjustment

        input_state = {
            "name": self.name,
            "value": self.last_value,
            "units": self.input_impl.units(),
            "date_servertime": datetime.now().strftime(constants.DATE_FORMAT),
            "date_utc": datetime.utcnow().strftime(
            constants.DATE_FORMAT)
        }

        fileio.log_input_state(self.name, input_state)

        if callback:
            callback(self, input_state)

        return input_state

    def calculate_async(self, complete):
        """calculate the input sensor value asynchronously"""
        thread = threading.Thread(target=self.calculate, args=[complete])
        thread.start()


class Output(object):

    """
    Class representing an output pin
    """

    def __init__(self, output_config):
        self.name = output_config["name"]
        self.controller = None
        self.input = output_config.get("input", None)
        self.mode = output_config["mode"]
        self.pin = output_config["pin"]
        self.debug_millis = 0

    def set_type(self, output_type, output_config, sample_ms):
        """creates the controller object based on the config settings"""
        output_handler = None
        output_type_controller = output_type["controller"]
        if output_type_controller == constants.PID_OUTPUT_CONTROLLER_TYPE:
            output_handler = PID.PidController(sample_time_ms=sample_ms,
                                               **output_type["config"])

            if output_config["mode"] == constants.TPC_OUTPUT:
                output_handler.set_output_limits(0, 100)
            elif output_config["mode"] == constants.PWM_OUTPUT:
                output_handler.set_output_limits(0, 100)
        else:
            raise Exception("Unknown output type '{}'".format(output_type))

        # setup the gpio pin
        RPIO.setup(output_config["pin"], RPIO.OUT, initial=RPIO.LOW)

        self.controller = output_handler

    def update_with_config(self, config):
        """update with new config"""
        # not yet merging in the updates
        # log(config)
        pass

    def set_pin_high(self):
        """set the gpio pin high"""
        self.debug_millis = millis()
        # log("set_pin_high: {}".format(self.debug_millis))
        if RPIO.gpio_function(self.pin) == RPIO.OUT:
            RPIO.output(self.pin, True)

    def set_pin_low(self):
        """set the gpio pin low"""
        mils = millis() - self.debug_millis
        log("set_pin_low: {}".format(mils))
        if RPIO.gpio_function(self.pin) == RPIO.OUT:
            RPIO.output(self.pin, False)

    def calculate(self, input_object, input_value, period_ms, loop_manager):
        """
        calculate and set output pin if required
        """
        self.controller.input = input_value
        value_computed = self.controller.compute()

        if self.controller.output == None or value_computed == False:
            return  # nothing to do with this controller

        if self.mode == constants.TPC_OUTPUT:
            # log("self.controller.output: {}".format(self.controller.output))
            if self.controller.output != 0:
                loop_manager.schedule_callback(self.set_pin_high, 0)

            # special case 100%, don't set it back low
            if self.controller.output != 100:
                loop_manager.schedule_callback(
                    self.set_pin_low, self.controller.output / 100.0 * period_ms)
        elif self.mode == constants.PWM_OUTPUT:
            # not yet implemented, tpc is probably adequate
            pass

        # write output values to state files
        output_state = {
            "name": self.name,
            "mode": self.mode,
            "output_value": self.controller.output,
            "input_value": self.controller.input,
            "input_name": input_object.name if input_object != None else None,
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
        self.controller.on_config_file_event(event)


class Controller(object):

    """
    Controller class
    """

    def __init__(self):
        self.controller_config = {}
        self.controller_config["config_current"] = False
        self.controller_config["programs_current"] = False
        self.controller_config["config_file_observer"] = None

        self.sample_ms = None
        self.inputs = {}
        self.outputs = {}
        self.programs = {}
        self.logs = []
        self.loop_manager = None

    def on_config_file_event(self, event):
        """called when a change occurs to any of the config files"""
        if isinstance(event, FileModifiedEvent):
            if "programs.js" in event.src_path:
                self.controller_config["programs_current"] = False
            else:
                self.controller_config["config_current"] = False

    def connect_logs(self, logs):
        """read the log config and create associated log objects"""
        del logs[:]

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

    def connect_inputs(self, input_dict):
        """
        read the input config and create associated input reading objects
        """
        input_dict.clear()

        for input_config in self.controller_config["inputs"]:
            if input_config["active"] != True:
                continue

            adjustment = None
            if "adjustment" in input_config:
                adjustment = input_config["adjustment"]

            io_input = Input(input_config["name"], adjustment)
            io_input.set_type(input_config["type"], input_config)

            input_dict[input_config["name"]] = io_input

    def connect_outputs(self, output_dict):
        """
        read the output config and create/update associated
        output pin control objects
        """
        # get the active outputs
        new_output_configs = [
            o for o in self.controller_config["outputs"] if o["active"]]

        current_output_objects = output_dict.values()

        new_output_names = [o["name"] for o in new_output_configs]
        to_remove = [
            o for o in current_output_objects if o.name not in new_output_names]

        # remove outputs that are no longer config'd
        for output in to_remove:
            log("removing: {}".format(output.name))
            del output_dict[output.name]

        # determine which config'd outputs already have an object
        existing_names = [o.name for o in current_output_objects]
        existing_configs = [
            c for c in new_output_configs if c["name"] in existing_names]

        # update existing outputs
        for existing_config in existing_configs:
            log("updateing output: {}".format(existing_config["name"]))
            existing_output = output_dict[existing_config["name"]]
            existing_output.update_with_config(existing_config)

            # remove from the new_output_configs list
            new_output_configs.remove(existing_config)

        # create new outputs
        for output_config in new_output_configs:
            log("creating output: {}".format(output_config["name"]))
            io_output = Output(output_config)
            io_output.set_type(
                output_config["type"], output_config, self.sample_ms)

            output_dict[output_config["name"]] = io_output

    def connect_programs(self):
        """
        read the program config and create associated program objects if needed
        """
        program_dict = {}

        for program_config in self.controller_config["programs"]:
            if program_config["active"] != True:
                continue

            prog = program.Program(program_config)

            program_dict[program_config["name"]] = prog

        return program_dict

    def read_controller_config(self):
        """
        read the controller level config file
        """
        # load the controller config
        self.controller_config.update(fileio.load_config_from_json_file(
            "config/controller.json"))

    def read_app_config(self):
        """
        load and read all the app configuration
        """
        if self.controller_config["config_current"] == True:
            return False

        config_file_observer = self.controller_config["config_file_observer"]
        if config_file_observer:
            config_file_observer.stop()

        config_file_observer = Observer()
        file_change_handler = ConfigFileWatcher(self)

        self.read_controller_config()

        # load the inputs config
        self.controller_config["inputs"] = fileio.load_config_from_json_file(
            "config/inputs.json")

        # load the outputs
        self.controller_config["outputs"] = fileio.load_config_from_json_file(
            "config/outputs.json")

        # load log configs
        self.controller_config["logs"] = fileio.load_config_from_json_file(
            "config/logs.json")

        config_file_observer.schedule(
            file_change_handler, "config", recursive=False)
        config_file_observer.start()

        self.controller_config["config_file_observer"] = config_file_observer
        self.controller_config["file_change_handler"] = file_change_handler
        self.controller_config["config_current"] = True

        return True

    def load_program_config(self):
        """loads the configuration for programs to run"""
        if self.programs != None and self.controller_config["programs_current"]:
            return

        self.controller_config["programs"] = fileio.load_config_from_json_file(
            "config/programs.json")

        self.programs = self.connect_programs()

    def evaluate_programs(self):
        """
        run any program logic that is needed
        """
        self.load_program_config()

        for prog in self.programs.values():
            changed = prog.run()

            if changed:
                self.controller_config["config_current"] = False

    def load_config_if_needed(self):
        """
        reload config and build objects if needed
        """
        if self.read_app_config():
            self.connect_inputs(self.inputs)
            self.connect_outputs(self.outputs)
            self.connect_logs(self.logs)

    def control(self, loop_callback=None):
        """
        main control loop method for the controller class
        """
        try:
            # do onetime setup, start by loading config
            self.read_controller_config()

            # set the sample_ms
            self.sample_ms = self.controller_config[
                "restart_required_config"]["control_sample_time_ms"]

            self.loop_manager = LoopManager(self.sample_ms)
            self.loop_manager.start()

            while True:
                self.loop_manager.begin_loop()

                # evaluate any active programs
                self.evaluate_programs()

                # reload app config if neede
                self.load_config_if_needed()

                # process the inputs
                input_objects = self.inputs.values()

                input_calculator = ParallelInputCalculator(
                    input_objects, self.logs)

                input_calculator.calculate_async()
                input_calculator.wait()

                # process outputs
                output_objects = self.outputs.values()

                for output in output_objects:
                    input_for_output = self.inputs.get(output.input, None)

                    if input_for_output != None:
                        input_value = input_for_output.last_value

                        output_state = output.calculate(input_for_output,
                                                        input_value,
                                                        self.sample_ms,
                                                        self.loop_manager)
                    else:
                        output_state = output.calculate(None,
                                                        None,
                                                        self.sample_ms,
                                                        self.loop_manager)

                    for logger in self.logs:
                        logger.log_output(output.name, output_state)

                if loop_callback != None:
                    loop_callback()

                self.loop_manager.next_iteration().wait()
        finally:
            RPIO.cleanup()

            self.controller_config["config_current"] = False
            if self.controller_config["config_file_observer"]:
                self.controller_config["config_file_observer"].stop()


class ParallelInputCalculator(object):

    """
    helper class to run async calculations of the inputs.
    some inputs take up to 1sec to return so running all
    of them in parallel to calculate them as quickly as possible
    """

    def __init__(self, inputs, logs):
        self.inputs = inputs
        self.event = threading.Event()
        self.count_lock = threading.Lock()
        self.logs = logs
        self.input_count = len(inputs)
        self.inputs_calculated = 0

    def calculate_async(self):
        """fire off async calc of all the inputs"""
        self.event.clear()

        if self.input_count > 0:
            for input_object in self.inputs:
                input_object.calculate_async(self.on_input_calculated)
        else:
            self.event.set()

    def on_input_calculated(self, input_object, input_state):
        """callback when an input is done calculating"""
        for logger in self.logs:
            logger.log_input(input_object.name, input_state)

        self.count_lock.acquire()
        self.inputs_calculated += 1

        if self.inputs_calculated == self.input_count:
            self.event.set()

        self.count_lock.release()

    def wait(self):
        """wait for all inputs to calculate"""
        self.event.wait()


class LoopManager(threading.Thread):

    """LoopManager manages when and how the controller loops"""

    def __init__(self, milliseconds):
        super(LoopManager, self).__init__()
        self.event = threading.Event()
        self.milliseconds = milliseconds
        self.daemon = True
        self.begin_ms = millis()
        self.callbacks = []
        self.callback_lock = threading.Lock()

    def run(self):
        self.event.clear()

        last_ms = millis()
        while True:
            now_ms = millis()
            if now_ms - last_ms > self.milliseconds:
                self.signal_loop()
                last_ms = now_ms

            self.execute_callbacks(now_ms)

            time.sleep(0.01)

    def execute_callbacks(self, now_ms):
        """
        executes any scheduled callbacks
        """
        self.callback_lock.acquire()
        callbacks_clone = self.callbacks[:]
        self.callback_lock.release()

        executed_callbacks = []
        for callback in callbacks_clone:
            if callback['ms'] == 0:
                # execute immediately
                callback['callback']()
                executed_callbacks.append(callback)
            else:
                start_ms = callback['start']
                if now_ms - start_ms > callback['ms']:
                    callback['callback']()
                    executed_callbacks.append(callback)

        self.callback_lock.acquire()
        for callback in executed_callbacks:
            self.callbacks.remove(callback)

        self.callback_lock.release()

    def schedule_callback(self, callback, milliseconds):
        """
        schedule a callback to be called after a given amount of time.
        callback will run on loop manager's thread
        """
        self.callback_lock.acquire()
        self.callbacks.append({
            'start': millis(),
            'ms': milliseconds,
            'callback': callback
        })
        self.callback_lock.release()

    def signal_loop(self):
        """signal the event"""
        self.event.set()

    def begin_loop(self):
        """a loop is beginning from the controller"""
        now_ms = millis()
        if now_ms - self.begin_ms > self.milliseconds * 1.01:
            print "Control loop logic took longer than config interval."

        self.begin_ms = now_ms
        self.event.clear()

    def next_iteration(self):
        """
        returns event for the control loop to wait on
        will probably do more stuff/logging here eventually
        """
        return self.event
