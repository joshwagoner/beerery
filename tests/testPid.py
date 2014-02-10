import unittest
import BeereryControl.pid as pid
import time

class PidTests(unittest.TestCase):
  def testPidController(self):
    p = pid.PidController(160, 2, 0.01, 0.01, 100)
    # p.mode = pid.PidController.MANUAL_MODE
    val = 60

    while True:
      p.input = val
      new_value = p.compute()
      if (p.output == None or new_value == False):
        time.sleep(.01)
        continue

      print p.output - 5
      val += ((p.output - 5) / 100.0)

      print "output {}".format(p.output)
      print "val {}\n".format(val)

      time.sleep(.01)

if __name__ == "__main__":
    unittest.main()
