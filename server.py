# 
# class for control server processes
# 
import time

app_params = {}
app_params_current = False

def connect_inputs():
  for input in app_params["inputs"]:
    print input

  return []

def read_app_params():
  global app_params
  global app_params_current

  if app_params_current == True:
    return False

  # todo: this should come from several json files
  app_params["control_sample_time_ms"] = 5000 # <- not sure if this should be global or on individual parts of the system
  app_params["logging_enabled"] = True

  app_params["inputs"] = [{
    "id": 0,
    "pin" : 23,
    "name" : "HLT",
    "type" : "thermistor",
    "log": "log_database"
  },
  {
    "id": 1,
    "pin" : 15,
    "name" : "MLT",
    "type" : "thermistor",
    "log": "log_database"
  },
  {
    "id": 2,
    "pin" : 13,
    "name" : "BK",
    "type" : "thermistor",
    "log": "log_database"
  }]

  app_params["outputs"] = [{
    "id": 0,
    "pin": 18,
    "active": False
    "name": "HLT",
    "type": {
      "controller": "PID",
      "config": "HLT_PID", # <- this should point to a seperate file (hlt_pid.json?) so that it can easily be reloaded?
      "input_id": 1
    },
    "log": "log_database"
  },
  {
    "id": 1,
    "pin": 8,
    "active": False
    "name": "BK",
    "type": {
      "controller": "PID",
      "config": "BK_PID", 
      "input_id": 2
    },
    "log": "log_database"
  }]

  app_params["configs"] = [{
    "id": "HLT_PID",
    "set_point": 160,
    "kp": 2, 
    "ki": 0.01, 
    "kd": 0.01
  },
  {
    "id": "BK_PID",
    "set_point": 205,
    "kp": 2, 
    "ki": 0.01, 
    "kd": 0.01
  }]

  app_params["logs"] = [{
    "id": "log_database"
    "store": {
      "type": "mongo_db",
      "connect_string": "mongo_db_connect"
    }
  }]

  print "app_params loaded:"
  print app_params

  app_params_current = True
  return True

def control():
  # do any onetime setup

  #setup config files polling

  while True:
    if read_app_params():
      inputs = connect_inputs()

      # create any needed output files that do not exist

      # connect logging backends - db, file, etc.

    # begin 
    print "heartbeat good"
    time.sleep(app_params["control_sample_time_ms"]/1000.0)
