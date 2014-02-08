import unittest
import BeereryControl.pid as pid
import time

class PidTests(unittest.TestCase):
  def testPidController(self):
    p = pid.PidController(10, 1, 0.1, 0.02, 1000)
    p.set_output_limits(-2,2)
    # p.mode = pid.PidController.MANUAL_MODE
    val = 5

    while True:
      p.input = val
      new_value = p.compute()
      if (p.output == None or new_value == False):
        time.sleep(.01)
        continue

      val += p.output

      print "output {}".format(p.output)
      print "val {}\n".format(val)

      time.sleep(.01)

if __name__ == "__main__":
    unittest.main()
