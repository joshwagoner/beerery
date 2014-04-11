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
# test onewire address: 28-000004f71e70
import beerery.controller as ctrl

class Runner(object):
  @patch('beerery.sensors.TempSensors.ThermistorSensor', autospec=True)
  @patch('beerery.sensors.TempSensors.OneWireTempSensor', autospec=True)
  @patch('beerery.sensors.TempSensors.TMP36TempSensor', autospec=True)
  def run(self, mock_tmp, mock_onewire, mock_thermistor):
    therm = mock_thermistor.return_value
    therm.get_temp.return_value = 55.25
    therm.units.return_value = "f"

    onewire = mock_onewire.return_value
    onewire.get_temp.return_value = 70.25
    onewire.units.return_value = "f"

    tmp = mock_tmp.return_value
    tmp.get_temp.return_value = 75.25
    tmp.units.return_value = "f"

    ctrl.control(self.onEachControlLoop)

  def onEachControlLoop(self):
    pass

r = Runner()
r.run()