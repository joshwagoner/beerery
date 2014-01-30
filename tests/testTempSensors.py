import unittest
from BeereryControl.sensors.TempSensors import TempSensor, ThermistorSensor

class TempSensorTests(unittest.TestCase):

  def testTempSensor(self):
    sensor = TempSensor()
    self.failUnless(sensor.get_temp() is None)

  def testThermistorSensor(self):
    sensor = ThermistorSensor(0)
    temp = sensor.get_temp(10,.01)

    print("temp {}".format(temp))

    self.failIf(sensor.get_temp(10, 0.01) == 0.0) 

  def main():
    unittest.main()

  if __name__ == '__main__':
    main()