import unittest
import BeereryControl

class SpiTests(unittest.TestCase):
  def testSpiInit(self):
  	read = BeereryControl.gpio.spireader.adc_read(0)
    self.failIf(read == 0)

  def testSpiRead(self):
  	read = BeereryControl.gpio.spireader.adc_read(0)
  	self.failIf(read == 0)

if __name__ == "__main__":
  unittest.main()
