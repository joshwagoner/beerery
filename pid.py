# 
# PID implementation based on posts in this series: 
# http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/
# 

import time
import sys

def millis():
  return int(round(time.time() * 1000))

def clamp(value, min, max):
    if value > max:
        value = max
    elif value < min:
        value = min

    return value

class PidController(object):
  AUTO_MODE = 1
  MANUAL_MODE = 0

  def __init__(self, set_point, kp, ki, kd, sample_time_ms):
    self.last_time = 0 # last time the pid function was calculated
    self.i_term = 0 # intergral term
    self.last_input = 0 # last input reading value
    self.kp = 0 # proportional gain
    self.ki = 0 # integral gain
    self.kd = 0 # derivative gain
    self.set_point = set_point 
    self.sample_time_ms = sample_time_ms
    self.min_out = 0
    self.max_out = 100 # by default the pid will return "duty cycle" between 0-100%
    self.mode = PidController.AUTO_MODE 
    self.input = 0
    self.output = 0

    self.set_params(kp, ki, kd)

  def set_mode(self, mode):
    move_to_auto = self.mode == PidController.MANUAL_MODE and mode == PidController.AUTO_MODE
    if move_to_auto:
        self.reinitialize()

    self.mode = mode

  def reinitialize(self):
    self.last_input = self.input
    self.i_term = clamp(self.output, self.min_out, self.max_out)

  def set_params(self, kp, ki, kd):
    sample_time_seconds = self.sample_time_ms / 1000.0
    self.kp = kp
    self.ki = ki * sample_time_seconds
    self.kd = kd / sample_time_seconds

  def set_output_limits(self, min, max):
    if (min > max):
        return

    self.min_out = min
    self.max_out = max

    # clamp running total to min/max
    self.i_term = clamp(self.i_term, self.min_out, self.max_out)

  def update_sample_time(self, sample_time_ms):
    if sample_time_ms > 0:
        ratio = sample_time_ms / self.sample_time_ms
        ki *= ratio
        kd /= ratio

        self.sample_time_ms = sample_time_ms

  def compute(self):
    if self.mode == PidController.MANUAL_MODE:
        self.output = None
        return False

    # calculate time since last compute
    now = millis()
    time_change = now - self.last_time

    if time_change >= self.sample_time_ms:
        print "time_change {}".format(time_change)

        # calc error
        error = self.set_point - self.input
        print "error {}".format(error)
        # add to running error total
        self.i_term += (self.ki * error)
        # clamp to min/max
        self.i_term = clamp(self.i_term, self.min_out, self.max_out)
        
        print "i_term {}".format(self.i_term)
        # input derivative
        d_input = self.input - self.last_input
        print "d_input {}".format(d_input)

        # save things for next time
        self.last_input = self.input
        self.last_time = now

        self.output = clamp(self.kp * error + self.i_term - self.kd * d_input, self.min_out, self.max_out)

        return True
    else:
        return False