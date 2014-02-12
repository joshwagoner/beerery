# 
# module for control server processes
#
# TODO: convert this to a class?
#
import time
import BeereryControl.sensors.TempSensors as TempSensors
import BeereryControl.pid as PID
from threading import Thread

# try import rpi libs, when under test may not load
import RPIO

THERMISTOR_INPUT_TYPE = "thermistor"
PID_OUTPUT_CONTROLLER_TYPE = "PID"
TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE = "TPC"
PULSE_WIDTH_MODULATION_OUTPUT_MODE = "PWM"

app_params = {}
app_params_current = False

inputs = []
outputs = []

class Input(object):
  def __init__(self, name, adc_channel, input_object):
    self.name = name
    self.adc_channel = adc_channel
    self.input_impl = input_object
    self.last_value = 0

class Output(object):
  def __init__(self, output_handler, **kwargs):
    # name, output_handler, input, pin, mode
    self.name = kwargs["name"]
    self.controller = output_handler
    self.input = kwargs["input"]
    self.mode = kwargs["mode"]
    self.pin = kwargs["pin"]
    self.active = kwargs["active"]

def connect_inputs():
  input_dict = {}

  for input in app_params["inputs"]:
    input_handler = None
    input_type = input["type"]
    if input_type == THERMISTOR_INPUT_TYPE:
      input_handler = TempSensors.ThermistorSensor(input["adc_channel"])
    else:
      raise Exception("Unknown input type '{}'".format(input_type))

    io_input = Input(input["name"], input["adc_channel"], input_handler)

    input_dict[input["name"]] = io_input

  return input_dict

def app_config_with_name(name):
  for config in app_params["configs"]:
    if config["name"] == name:
      return config

  return None

def connect_outputs():
  output_dict = {}

  for output in app_params["outputs"]:
    if output["active"] != True:
        continue

    output_handler = None
    output_type = output["type"]
    output_type_controller = output_type["controller"]
    if output_type_controller == PID_OUTPUT_CONTROLLER_TYPE:
      output_handler = PID.PidController(sample_time_ms=app_params["control_sample_time_ms"], **app_config_with_name(output_type["config"])) #TODO: update PidController to take a dictionary input

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

def read_app_params():
  global app_params
  global app_params_current

  if app_params_current == True:
    return False

  # todo: this should come from several json files, and be an argument somewhere to support testing
  app_params["control_sample_time_ms"] = 5000 # <- not sure if this should be global or on individual parts of the system, global for now though
  app_params["logging_enabled"] = True

  app_params["inputs"] = [{
    "adc_channel" : 0,
    "name" : "HLT",
    "type" : "thermistor",
    "log": "log_database"
  },
  {
    "adc_channel" : 1,
    "name" : "MLT",
    "type" : "thermistor",
    "log": "log_database"
  },
  {
    "adc_channel" : 2,
    "name" : "BK",
    "type" : "thermistor",
    "log": "log_database"
  }]

  app_params["outputs"] = [{
    "pin": 25,
    "active": True,
    "name": "HLT",
    "type": {
      "controller": "PID",
      "config": "HLT_PID" # <- this should point to a seperate file (hlt_pid.json?) so that it can easily be reloaded?
    },
    "input": "MLT",
    "mode": TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE,
    "log": "log_database"
  },
  {
    "id": 1,
    "pin": 8,
    "active": False,
    "name": "BK",
    "type": {
      "controller": "PID",
      "config": "BK_PID"
    },
    "input": "BK",
    "mode": TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE,
    "log": "log_database"
  }]

  app_params["configs"] = [{
    "name": "HLT_PID",
    "set_point": 52,
    "kp": 50, 
    "ki": 0.025, 
    "kd": 0.05
  },
  {
    "name": "BK_PID",
    "set_point": 70,
    "kp": 25, 
    "ki": 5, 
    "kd": 5
  }]

  app_params["logs"] = [{
    "name": "log_database",
    # "store": {
    #   "type": "mongo_db",
    #   "connect_string": "mongo_db_connect"
    # }
    "store": {
      "type": "file",
      "path": "~/beerery_log.json"
    }
  }]

  # print "app_params loaded:"
  # print app_params

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
  # do any onetime setup

  #TODO: setup config files polling, not yet supported, requires full restart

  try: 
    while True:
      if read_app_params():
        inputs = connect_inputs()
        outputs = connect_outputs();

        # create any needed output files that do not exist

        # connect logging backends - db, file, etc.

      # begin 
      print "Processing..."

      # sample input values
      input_objects = inputs.values()

      sample_count = 10 # <- make sample count configurable
      sample_interval_s = 0.01 # <- make sample sleep amount configurable

      for input in input_objects:
        input.input_impl.reset()

      for x in xrange(0,sample_count): 
        for input in input_objects:
          input.input_impl.sample()
        time.sleep(sample_interval_s) 

      for input in input_objects:
        input.last_value = input.input_impl.value_from_samples()
        print input.last_value

      # write input values to state files, async

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
            continue # nothing to do with this controller
          
          if output.mode == TIME_PROPORTIONAL_CONTROL_OUTPUT_MODE:
            set_pin_for_ms(output.pin, output_controller.output/100*app_params["control_sample_time_ms"])
          elif output.mode == PULSE_WIDTH_MODULATION_OUTPUT_MODE:
            pass #not yet implemented

        # print "Input for output '{}' = '{}'".format(output.name, input_for_output.name)

      if loop_callback != None:
        loop_callback()

      print "Sleeping..."

      time.sleep(app_params["control_sample_time_ms"]/1000.0 - (sample_count * sample_interval_s + sample_interval_s))
  finally:
    RPIO.cleanup()

    global app_params_current
    app_params_current = False