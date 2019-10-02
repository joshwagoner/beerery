"""
mocked controller for running without real inputs and outputs
"""
import mock
from mock import patch
import sys
import os
import random

#  mock several modules to enable running on os x
RPIO_MOCK = mock.Mock()
sys.modules['RPIO'] = RPIO_MOCK
sys.modules['spidev'] = mock.Mock()

os.system = mock.Mock()
# test onewire address: 28-000004f65c4d
from beerery.controller import Controller


class Runner(object):

    """
    Test runner for running controller on non-raspberry pi machine
    """

    def __init__(self):
        self.thermistor = None
        self.onewire = None
        self.tmp = None

    @patch('beerery.sensors.tempsensors.ThermistorSensor', autospec=True)
    @patch('beerery.sensors.tempsensors.OneWireTempSensor', autospec=True)
    @patch('beerery.sensors.tempsensors.TMP36TempSensor', autospec=True)
    def run(self, mock_tmp, mock_onewire, mock_thermistor):
        """run controller with mocked sensors"""
        self.thermistor = mock_thermistor.return_value
        self.thermistor.get_temp.return_value = 55.25
        self.thermistor.units.return_value = "f"

        self.onewire = mock_onewire.return_value
        self.onewire.get_temp.return_value = 152
        self.onewire.units.return_value = "f"

        self.tmp = mock_tmp.return_value
        self.tmp.get_temp.return_value = 75.25
        self.tmp.units.return_value = "f"

        ctrl = Controller()
        ctrl.control(self.on_each_control_loop)

    def on_each_control_loop(self):
        """ code to run on each control loop"""
        self.thermistor.get_temp.return_value += random.uniform(-2.0, 2.0)
        self.onewire.get_temp.return_value += random.uniform(
            0.1, 0.5)  # random.uniform(-2.0, 2.0)
        self.tmp.get_temp.return_value += random.uniform(-2.0, 2.0)

r = Runner()
r.run()
