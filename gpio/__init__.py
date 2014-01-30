import spidev

class spireader:
	_refVoltage = 3.324
	_spi = None

	@staticmethod
	def initSpi():
		if (spireader._spi == None):
			spireader._spi = spidev.SpiDev()
			spireader._spi.open(0,0)

	@staticmethod
	def adc_read(channel):
		spireader.initSpi()
		adc = spireader._spi.xfer2([1,(8+channel)<<4,0])
		data = ((adc[1]&3) << 8) + adc[2]
		return data

	@staticmethod
	def adc_to_volts(data):
		volts = (data / 1023.0) * spireader._refVoltage
		volts = round(volts, 4)
		return volts

	@staticmethod
	def adc_read_as_volts(channel):
		data = spireader.adc_read(channel)
		return adc_to_volts(data)

	@staticmethod
	def reference_voltage():
		return spireader._refVoltage