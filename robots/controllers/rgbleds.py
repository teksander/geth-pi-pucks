#!/usr/bin/env python3
import smbus
import sys
import time
import logging
import threading

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

I2C_CHANNEL = 3
FT903_I2C_ADDR = 0x1C

NOP_TIME = 0.000001

bus = None

def __nop_delay(t):
	time.sleep(t * NOP_TIME)

def e_init_rgb():
	global bus
	while True:
		try:
			bus = smbus.SMBus(I2C_CHANNEL)
			return
		except:
			trials+=1
			if(trials == 5):
				logger.critical('Error initializing RGB')
				sys.exit(1)

def write_byte_data(register, data):
	trials = 0
	while True:
		try:
			bus.write_byte_data(FT903_I2C_ADDR, register, data)
			__nop_delay(10000)
			return
		except:
			trials+=1
			if(trials == 5):
				logger.error('I2C RGB write error occured')
				return

class RGBLEDs(object):
	""" Interact with the 3 RGB leds on the top of the pi-puck
	"""
	def __init__(self):
		""" Constructor
		"""
		self.__stop = 1	
		self.led1 = 0x00
		self.led2 = 0x01
		self.led3 = 0x02
		self.all = [0x00,0x01,0x02]
		self.red = 0x01
		self.green = 0x02
		self.blue = 0x04
		self.off = 0x00
		self.white = 0x07
		self.frozen = False

		# /* Init FT903 I2C Interface */
		e_init_rgb()
		
		self.setLED(self.all, 3*[self.off])

	def _from_string(self, string):
		if string == 'red': return self.red
		if string == 'green': return self.green
		if string == 'blue': return self.blue
		if string == 'white': return self.white	
			
	def setAll(self, color):

		if isinstance(color, str):
			color = self._from_string(color)

		if not self.frozen:
			write_byte_data(self.led1, color)
			write_byte_data(self.led2, color)
			write_byte_data(self.led3, color)

	def setLED(self, LED, RGB):
		if not self.frozen:
			for i in range(len(LED)):
				write_byte_data(LED[i], RGB[i])


	def flashRed(self, delay=1):
		if not self.frozen:
			self.setLED(self.all, 3*[self.red])
			time.sleep(delay)
			self.setLED(self.all, 3*[self.off])

	def flashGreen(self, delay=1):
		if not self.frozen:
			self.setLED(self.all, 3*[self.green])
			time.sleep(delay)
			self.setLED(self.all, 3*[self.off])

	def flashBlue(self, delay=1):
		if not self.frozen:
			self.setLED(self.all, 3*[self.blue])
			time.sleep(delay)
			self.setLED(self.all, 3*[self.off])

	def flashWhite(self, delay=1):
		if not self.frozen:
			self.setLED(self.all, 3*[self.white])
			time.sleep(delay)
			self.setLED(self.all, 3*[self.off])
			
	def flashWhiteThreaded(self, delay=1):
		thread = threading.Thread(target=self.flashWhite, args=(delay,))
		thread.start()
		
	def freeze(self):
		self.frozen = True

	def unfreeze(self):
		self.frozen = False

	def stop(self):
		self.unfreeze()
		self.setLED([0x00,0x01,0x02], [0x00,0x00,0x00])
		bus.close()

# This can be used to make a quick LED signal
if __name__ == "__main__":

	rgb = RGBLEDs()
	rgb.setLED(rgb.all, 3*[rgb.red])
	time.sleep(15)
	rgb.stop()

