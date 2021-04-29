#!/usr/bin/env python3
import time
import sys
import smbus

class RGBLEDs(object):
	""" Request a measurement from the Ground Sensors
	GroundSensor.getNew() returns the measurement of each sensor
	"""
	def __init__(self):
		""" Constructor
		"""
		self.__stop = 1	
		self.I2C_CHANNEL = 3
		self.FT903_I2C_ADDR = 0x1C
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

		try:
			self.bus = smbus.SMBus(self.I2C_CHANNEL)
			self.setLED(self.all, 3*[self.off])
		except:
			print('RGB Failed')

	def setLED(self, LED, RGB):
		# try:
		if not self.frozen:
			for i in range(len(LED)):
				self.bus.write_byte_data(self.FT903_I2C_ADDR, LED[i], RGB[i])
		# except:
		# 	pass

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

	def freeze(self):
		self.frozen = True

	def unfreeze(self):
		self.frozen = False

	def stop(self):
		self.unfreeze()
		self.setLED([0x00,0x01,0x02], [0x00,0x00,0x00])
		self.bus.close()
