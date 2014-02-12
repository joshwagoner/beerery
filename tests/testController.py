import unittest
import mock
from mock import patch
import time
import sys

#  mock the RPIO & spidev modules
# rpio_mock = mock.Mock()
# sys.modules['RPIO'] = rpio_mock
# sys.modules['spidev'] = mock.Mock()

import BeereryControl.controller as ctrl
import BeereryControl.sensors.TempSensors as TempSensors

class ServerTests(unittest.TestCase):
  @patch('BeereryControl.sensors.TempSensors.ThermistorSensor', autospec=True)
  def testServer(self, mock_thermistor):
    self.thermistor_mocks = [mock.Mock(), mock.Mock(), mock.Mock()]
    self.thermistor_mocks[0].value_from_samples.return_value = 50
    self.thermistor_mocks[1].value_from_samples.return_value = 50
    self.thermistor_mocks[2].value_from_samples.return_value = 50
    mock_thermistor.side_effect = self.thermistor_mocks

    ctrl.control(self.onEachControlLoop)

  def onEachControlLoop(self):
    # assert methods called
    # rpioMock = sys.modules['RPIO']
    # rpioMock.setup.assert_called_with(25, rpio_mock.OUT, initial=rpio_mock.LOW), 'RPIO.setup was not properly called'

    # rpioMock.output.assert_called_with(25, True);

    # self.thermistor_mocks[0].value_from_samples.return_value += 1
    # amount of change in water temperature for 1 gal/minute with 5500w element: 35.67114853
    # simulating 10 gallon, 10gal change per minute: 3.567114853, per second: .059451914
    self.thermistor_mocks[1].value_from_samples.return_value += ((.059451914 * ctrl.outputs["HLT"].controller.output/100*5) - 0.01)

if __name__ == "__main__":
    unittest.main()
