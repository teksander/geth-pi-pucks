#!/usr/bin/env python3
import smbus
import time
import threading
import logging

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

I2C_CHANNEL = 4
GS_I2C_ADDR = 0x60

NOP_TIME = 0.000001

bus = None

def __nop_delay(t):
	time.sleep(t * NOP_TIME)

def e_init_gs():
	global bus
	while True:
		try:
			bus = smbus.SMBus(I2C_CHANNEL)
			return
		except:
			trials+=1
			if(trials == 25):
				logger.critical('Error initializing GS')

def __read_reg(reg, count):
	data = bytearray([0] * 6)
	trials=0
	while True:
		try:			
			data = bus.read_i2c_block_data(GS_I2C_ADDR, reg, count)
			__nop_delay(10000)
			return data
		except:
			trials+=1
			logger.warning('GS I2C failed. Trials=%i', trials)	
			__nop_delay(10000)
			if trials == 25:
				logger.error('GS I2C read error')
				return None

def get_readings():
	rawValues = [None for x in range(3)]
	
	# Retrieve ground data
	groundData = __read_reg(0, 6)

	# Process data
	if groundData != None:
		rawValues[0] = (groundData[1] + (groundData[0]<<8))
		rawValues[1] = (groundData[3] + (groundData[2]<<8))
		rawValues[2] = (groundData[5] + (groundData[4]<<8))

	for i in range(3):
		if rawValues[i] > 1500:
			rawValues[i] = 0
			
	return rawValues

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
		self.groundValues = [0 for x in range(3)]
		self.groundCumsum = [0 for x in range(3)]
		self.count = 0

		# Parameters obtained from calibration
		self.whiteCalib = 3* [1000]
		self.blackCalib = 3* [0]
		self.calibFactor= 3* [1]

		e_init_gs()
		logger.info('Ground-Sensor OK')


	def step(self):
		# Collect new values
		self.rawValues = get_readings()

		# Perform calibrated correction (not implemented in this manner)
		self.groundValues = self.rawValues

		# Compute cumulative sum
		self.groundCumsum[0] += self.groundValues[0] 
		self.groundCumsum[1] += self.groundValues[1]
		self.groundCumsum[2] += self.groundValues[2]
		self.count += 1

	def __sensing(self):
		""" This method runs in the background until program is closed 
		"""  

		while True:
			stTime = time.time()

			self.step()

			if self.__stop:
				break 
			else:
				# Read frequency @ 20 Hz.
				dfTime = time.time() - stTime
				if dfTime < (1/self.freq):
					time.sleep((1/self.freq) - dfTime)

	def getAvg(self):
		""" This method returns the average ground value since last call """

		if self.__stop:
			logger.warning('getAvg: Ground Sensor is OFF')
			return None

		else:
			try:
				groundAverage =  [round(x/self.count) for x in self.groundCumsum]
			except:
				groundAverage = None
			else:
				self.count = 0
				self.groundCumsum = 3* [0]
			return groundAverage

	def getNew(self):
		""" This method returns the instant ground value """

		if self.__stop:
			logger.warning('getNew: Ground Sensor is OFF')
			return None

		else:
			return self.groundValues;

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
			logger.warning('Ground-Sensor already ON')

	def stop(self):
		""" This method is called before a clean exit """
		self.__stop = 1
		self.thread.join()

		bus.close()
		logger.info('Ground-Sensor OFF') 

	def calibration(self, rawValues):
		correctedValues = 3* [None]

		for i, rawValue in enumerate(rawValues):
			correctedValues[i] = round((rawValue - self.blackCalib[i]) * self.calibFactor[i])

		return correctedValues

if __name__ == "__main__":

	gs = GroundSensor()
	gs.start()

	while True:
		print(gs.getAvg())
		time.sleep(0.2)