# 
# module for control server processes
#
# TODO: convert this to a class?
#
import time
from datetime import datetime
import beerery.sensors.TempSensors as TempSensors
import beerery.loggers as loggers
import beerery.pid as PID
import json
from pprint import pprint
from threading import Thread
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import RPIO

THERMISTOR_INPUT_TYPE = "thermistor"
ONEWIRE_TEMP_INPUT_TYPE = "DS18B20"
TMP36_TEMP_INPUT_TYPE = "TMP36"
PID_OUTPUT_CONTROLLER_TYPE = "PID"
TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE = "TPC"
PULSE_WIDTH_MODULATION_OUTPUT_MODE = "PWM"
MONGODB_LOG = "mongodb"

app_params = {}
app_params_current = False
config_file_observer = None

inputs = []
outputs = []

class Input(object):
  def __init__(self, name, input_object, units, adjustment):
    self.name = name
    self.input_impl = input_object
    self.last_value = 0
    self.units = units
    self.adjustment = adjustment

class Output(object):
  def __init__(self, output_handler, **kwargs):
    # name, output_handler, input, pin, mode
    self.name = kwargs["name"]
    self.controller = output_handler
    self.input = kwargs["input"]
    self.mode = kwargs["mode"]
    self.pin = kwargs["pin"]
    self.active = kwargs["active"]

class ConfigFileWatcher(FileSystemEventHandler):
  def on_any_event(self, event):
    global app_params_current
    app_params_current = False

def connect_logs():
  logs = []

  if not app_params["logging_enabled"]:
    return logs

  for log in app_params["logs"]:
    logger = None
    log_type = log["type"]
    if log_type == MONGODB_LOG:
      logger = loggers.MongoDBLogger(log["db_uri"], log["database"])
    else:
      raise Exception("Unknown log type '{}'".format(log_type))

    logs.append(logger)

  return logs

def connect_inputs():
  input_dict = {}

  for input in app_params["inputs"]:
    if input["active"] != True:
        continue
    
    input_handler = None
    input_type = input["type"]
    if input_type == THERMISTOR_INPUT_TYPE:
      input_handler = TempSensors.ThermistorSensor(input["adc_channel"])
    elif input_type == ONEWIRE_TEMP_INPUT_TYPE:
      input_handler = TempSensors.OneWireTempSensor(input["address"])
    elif input_type == TMP36_TEMP_INPUT_TYPE:
      input_handler = TempSensors.TMP36TempSensor(input["adc_channel"])
    else:
      raise Exception("Unknown input type '{}'".format(input_type))

    adjustment = None
    if "adjustment" in input:
      adjustment = input["adjustment"]

    io_input = Input(input["name"], input_handler, input_handler.units(), adjustment)

    input_dict[input["name"]] = io_input

  return input_dict

def connect_outputs():
  output_dict = {}

  for output in app_params["outputs"]:
    if output["active"] != True:
        continue

    log("output: {}".format(output["name"]))
    output_handler = None
    output_type = output["type"]
    output_type_controller = output_type["controller"]
    if output_type_controller == PID_OUTPUT_CONTROLLER_TYPE:
      output_handler = PID.PidController(sample_time_ms=app_params["control_sample_time_ms"], **output_type["config"])

      if output["mode"] == TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE:
        output_handler.set_output_limits(0, 100) #app_params["control_sample_time_ms"])
      elif output["mode"] == PULSE_WIDTH_MODULATION_OUTPUT_MODE:
        output_handler.set_output_limits(0, 100)
    else:
      raise Exception("Unknown output type '{}'".format(input_type))

    # setup the gpio pin
    RPIO.setup(output["pin"], RPIO.OUT, initial=RPIO.LOW)

    io_output = Output(output_handler, **output)

    output_dict[output["name"]] = io_output

  return output_dict

def log(message):
  # pprint(message)
  pass

def load_param_from_json_file(config_name, file_path, log_name):
  log("loading {}...".format(log_name))
  
  input_json = open(file_path)
  dict_from_json = json.load(input_json)
  if (config_name):
    app_params[config_name] = dict_from_json
  input_json.close()
  
  log("{} loaded.".format(log_name))
  log(" data:")
  log(dict_from_json)

  return dict_from_json

def read_app_params():
  global app_params
  global app_params_current
  global config_file_observer

  if app_params_current == True:
    return False

  if config_file_observer:
    config_file_observer.stop()

  config_file_observer = Observer()
  file_change_handler = ConfigFileWatcher()

  controller_config = load_param_from_json_file(None, "config/controller.json", "controller config")
  app_params.update(controller_config)

  # load the inputs config
  load_param_from_json_file("inputs", "config/inputs.json", "inputs")

  # load the outputs
  load_param_from_json_file("outputs", "config/outputs.json", "outputs")

  # load log configs
  load_param_from_json_file("logs", "config/logs.json", "logs")

  config_file_observer.schedule(file_change_handler, "config", recursive=False);
  config_file_observer.start()

  app_params_current = True
  return True

def signal_pin_for_ms(pin, ms):
  # set the pin high
  RPIO.output(pin, True)

  # sleep
  time.sleep(ms/1000)

  #set it back low
  if RPIO.gpio_function(pin) == RPIO.OUT:
    RPIO.output(pin, False)

def set_pin_for_ms(pin, ms):
  t = Thread(target=signal_pin_for_ms, args=(pin, ms))
  t.start();

def control(loop_callback=None):
  global inputs
  global outputs
  global app_params
  # do any onetime setup

  try: 
    while True:
      if read_app_params():
        inputs = connect_inputs()
        outputs = connect_outputs()
        logs = connect_logs()

      # start with the inputs
      input_objects = inputs.values()

      for input in input_objects:
        input.last_value = input.input_impl.get_temp()

        if input.adjustment:
          input.last_value += input.adjustment

        # write input values to state files
        # TODO: maybe make this async via pushing onto separate thread, eventually.
        #       should probably also write to a temp file and then atomically move to "current" file
        input_state = {
          "name": input.name,
          "value": input.last_value,
          "units": input.units,
          "date_servertime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "date_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") 
        }

        with open("state/input_{}.json".format(input.name), 'w+') as outfile:
          json.dump(input_state, outfile)

        for logger in logs:
          logger.log_input(input.name, input_state)

      # process outputs
      output_objects = outputs.values()

      for output in output_objects:
        input_for_output = inputs[output.input]
        output_controller = output.controller

        if input_for_output != None:
          input_value = input_for_output.last_value

          output_controller.input = input_value
          value_computed = output_controller.compute()

          if (output_controller.output == None or value_computed == False):
            log("skipping output '{}': output_controller.output = {}, value_computed = {}".format(output.name, output_controller.output, value_computed))
            continue # nothing to do with this controller
          
          if output.mode == TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE:
            set_pin_for_ms(output.pin, output_controller.output/100*app_params["control_sample_time_ms"])
          elif output.mode == PULSE_WIDTH_MODULATION_OUTPUT_MODE:
            pass #not yet implemented, tpc is probably adequate

          # write output values to state files
          # TODO: as above maybe make this async
          output_state = {
            "name": output.name,
            "mode": output.mode,
            "output_value": output_controller.output,
            "input_value": output_controller.input,
            "input_name": input_for_output.name,
            "date_servertime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") 
          }

          with open("state/output_{}.json".format(output.name), 'w+') as outfile:
            json.dump(output_state, outfile)

          for logger in logs:
            logger.log_output(output.name, output_state)

      if loop_callback != None:
        loop_callback()

      # TODO: keep track of how long the above takes and subtract that from the sleep time
      time.sleep(app_params["control_sample_time_ms"]/1000.0)
  finally:
    RPIO.cleanup()

    global app_params_current
    app_params_current = False

    global config_file_observer
    config_file_observer.stop()