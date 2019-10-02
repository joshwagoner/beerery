import time
import math
from beerery.gpio import spireader
import os
import random

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

ONE_WIRE_BASE_DIR = '/sys/bus/w1/devices/'


def thermistor_ohm_to_f(x):
    A = 0.0011371549  # 0.00116597
    B = 0.0002325949  # 0.000220635
    C = 0  # 1.81284e-06
    D = 9.54e-8  # 2.73396e-09
    r = math.log(x)
    k = 1.0 / (A + B * r + C * r ** 2 + D * r ** 3)  # to c: - 273.15

    return (k - 273.15) * 1.8000 + 32.00  # to f


class TempSensor(object):

    def __init__(self):
        pass

    def get_temp(self):
        pass

    def units(self):
        return "f"


class ThermistorSensor(TempSensor):

    def __init__(self, adc_channel):
        self.adc_sample_total = 0
        self.adc_sample_count = 0
        self.adc_channel = adc_channel
        self.series_resistor = 10000

    def sample(self):
        self.adc_sample_total += spireader.adc_read(self.adc_channel)
        self.adc_sample_count += 1

    def reset(self):
        self.adc_sample_total = 0
        self.adc_sample_count = 0

    def value_from_samples(self):
        adc_average = self.adc_sample_total / self.adc_sample_count
        volts = spireader.adc_to_volts(adc_average)

        temp = 0

        if volts:
            thermistor_ohms = round(
                (spireader.reference_voltage() * self.series_resistor / volts) - self.series_resistor)
            temp = thermistor_ohm_to_f(thermistor_ohms)

        return temp

    def get_temp(self):
        self.reset()

        sample_count = 10
        sample_sleep_s = 0.01

        for x in xrange(0, sample_count):
            self.sample()
            time.sleep(sample_sleep_s)

        return self.value_from_samples()


class TMP36TempSensor(TempSensor):

    def __init__(self, adc_channel):
        self.adc_channel = adc_channel

    def get_temp(self):
        adc_read = spireader.adc_read(self.adc_channel)
        volts = spireader.adc_to_volts(adc_read)

        temp = 0

        if volts:
            temp_c = (volts - 0.5) * 100.0
            temp = temp_c * 1.8 + 32.0

        print volts

        return temp


class OneWireTempSensor(TempSensor):

    def __init__(self, address):
        self.address = address
        self.device_folder = ONE_WIRE_BASE_DIR + self.address
        self.device_file = self.device_folder + '/w1_slave'

    def read_temp_file(self):
        """read the virtual file that exposes the sensor value"""
        file_obj = open(self.device_file, 'r')
        lines = file_obj.readlines()
        file_obj.close()
        return lines

    def get_temp(self):
      try:
        lines = self.read_temp_file()
        if lines[0].strip()[-3:] != 'YES':
            return 0
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return temp_f
      except: 
        time.sleep(random.uniform(1, 2))
        return 0

    def timed_get_temp(self):
        """time how long it takes to get the temp"""
        time0 = time.time()
        temp = self.get_temp()
        time1 = time.time()

        print time1 - time0

        return temp
