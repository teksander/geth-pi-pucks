#!/usr/bin/env python3
from smbus import SMBus
import sys
import time
import threading

class GroundSensor(object):
	""" Set up a ground-sensor data acquisition loop on a background thread
	The __sensing() method will be started and it will run in the background
	until the application exits.
	"""
	def __init__(self, freq = 20):
		""" Constructor
		:type freq: str
		:param freq: frequency of measurements in Hz (tip: 20Hz)
		"""
		self.__stop = 1	
		self.freq = freq
		self.groundValue = [0 for x in range(3)]
		self.groundCumsum = [0 for x in range(3)]
		self.count = 0
		self.failed = 0

	def __read_reg(self, reg, count):
		data = bytearray([0] * 6)
		trials=0
		while True:
			try:			
				data = self.__bus.read_i2c_block_data(self.__GROUNDSENSOR_ADDRESS, reg, count)
				self.failed = 0
				return data
			except:
				trials+=1
				time.sleep(0.1)
				if trials == 5:
					print('GS I2C read error occured')
					self.failed = 1	
					return None

	def __sensing(self):
		""" This method runs in the background until program is closed 
		"""  

		I2C_CHANNEL = 4
		self.__GROUNDSENSOR_ADDRESS = 0x60  # Device address
		self.__bus = None

		try:
			self.__bus = SMBus(I2C_CHANNEL)
		except:
			print("Ground Sensor Error")

		while True:
			# Initialize variables
			stTime = time.time()
			self.groundValue = [None for x in range(3)]
			
			# Retrieve ground data
			groundData = self.__read_reg(0, 6)

			# Process data
			if groundData != None:
				self.groundValue[0] = (groundData[1] + (groundData[0]<<8))
				self.groundValue[1] = (groundData[3] + (groundData[2]<<8))
				self.groundValue[2] = (groundData[5] + (groundData[4]<<8))

				# Compute cumulative sum
				self.groundCumsum[0] += self.groundValue[0] 
				self.groundCumsum[1] += self.groundValue[1]
				self.groundCumsum[2] += self.groundValue[2]
				self.count += 1

			if self.__stop:
				break 
			else:
				# Read frequency @ 20 Hz.
				dfTime = time.time() - stTime
				if dfTime < (1/self.freq):
					time.sleep((1/self.freq) - dfTime)

	def getAvg(self):
		""" This method returns the average ground value since last call """

		# Compute average
		try:
			groundAverage =  [round(x/self.count) for x in self.groundCumsum]
		except:
			groundAverage = None
		if self.__stop:
			print('Error: Ground Sensor is OFF')
			return None
		else:
			self.count = 0
			self.groundCumsum = [0 for x in range(3)]
			return groundAverage

	def getNew(self):
		""" This method returns the instant ground value """
		if self.__stop:
			print('Error: Ground Sensor is OFF')
			return None
		else:
			return self.groundValue;


	def hasFailed(self):
		""" This method returns wether the module failed """
		return self.failed

	def start(self):
		""" This method is called to start __sensing """
		if self.__stop:
			self.__stop = 0
			# Initialize background daemon thread
			self.thread = threading.Thread(target=self.__sensing, args=())
			self.thread.daemon = True 

			# Start the execution                         
			self.thread.start()   
		else:
			print('Ground-Sensor already ON')

	def stop(self):
		""" This method is called before a clean exit """
		self.__stop = 1
		self.thread.join()
		self.__bus.close()
		print('Ground-Sensor OFF') 