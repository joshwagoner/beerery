import spidev  # only available on the raspberry pi, pylint: disable=F0401


class spireader:

    """class containing collection of spi related functions"""
    _refVoltage = 3.3
    _spi = None

    @staticmethod
    def init_spi():
        """initialize spi system"""
        if spireader._spi == None:
            spireader._spi = spidev.SpiDev()
            spireader._spi.open(0, 0)

    @staticmethod
    def adc_read(channel):
        """read from an ADC channel"""
        spireader.init_spi()
        adc = spireader._spi.xfer2([1, (8 + channel) << 4, 0])
        data = ((adc[1] & 3) << 8) + adc[2]
        return data

    @staticmethod
    def adc_to_volts(data):
        """convert ADC reading to voltage"""
        volts = (data / 1023.0) * spireader._refVoltage
        volts = round(volts, 10)
        return volts

    @staticmethod
    def adc_read_as_volts(channel):
        """read ADC value and convert to volts"""
        data = spireader.adc_read(channel)
        return spireader.adc_to_volts(data)

    @staticmethod
    def reference_voltage():
        """return the reference voltage to use in ADC calculations"""
        return spireader._refVoltage
