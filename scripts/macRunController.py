import mock
from mock import patch
import time
import sys
import os 

#  mock several modules to enable running on os x
rpio_mock = mock.Mock()
sys.modules['RPIO'] = rpio_mock
sys.modules['spidev'] = mock.Mock()

os.system = mock.Mock();

import BeereryControl.controller as ctrl

class Runner(object):
  @patch('BeereryControl.sensors.TempSensors.ThermistorSensor', autospec=True)
  @patch('BeereryControl.sensors.TempSensors.OneWireTempSensor', autospec=True)
  def run(self, mock_onewire, mock_thermistor):
    therm = mock_thermistor.return_value
    therm.value_from_samples.return_value = 55.25
    therm.units.return_value = "f"

    onewire = mock_onewire.return_value
    onewire.value_from_samples.return_value = 70.25
    onewire.units.return_value = "f"

    ctrl.control(self.onEachControlLoop)

  def onEachControlLoop(self):
    pass

r = Runner()
r.run()