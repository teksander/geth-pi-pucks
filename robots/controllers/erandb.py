#!/usr/bin/env python3
import smbus
import sys
import time
import threading
import logging
import sys
import traceback

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

I2C_CHANNEL = 4
RB_I2C_ADDR = 0x20

NOP_TIME = 0.000001

bus = None

ON_BOARD = 0
ON_ROBOT = 1
__data_length = 16

# Version modified for self-diagnosis. Temporary fix to GCTRonics problems
def __write_data(addr, data):
	# try:
	bus.write_byte_data(RB_I2C_ADDR, addr, data)
	__nop_delay(10000)
	# except:
	# 	logger.error('RaB I2C write error occured')
	# 	raise
	# return

def __read_data(addr):
	data = None
	# try:
	data = bus.read_byte_data(RB_I2C_ADDR, addr)
	__nop_delay(10000)
	# except:
	# 	logger.error('RaB I2C write error occured')
	# 	raise

	return data


# def __write_data(addr, data):
# 	trials = 0
# 	while True:
# 		try:
# 			bus.write_byte_data(RB_I2C_ADDR, addr, data)
# 			__nop_delay(10000)
# 			return
# 		except:
# 			trials+=1
# 			logger.warning('RaB I2C failed. Trials=%i', trials)
# 			__nop_delay(10000)
# 			if(trials == 25):
# 				logger.error('RaB I2C write error occured')
# 				return

# def __read_data(addr):
# 	trials = 0
# 	while True:
# 		try:
# 			data = bus.read_byte_data(RB_I2C_ADDR, addr)
# 			__nop_delay(10000)
# 			return data
# 		except:
# 			trials+=1
# 			logger.warning('RaB I2C failed. Trials=%i', trials)		
# 			__nop_delay(10000)
# 			if(trials == 25):
# 				logger.error('RaB I2C read error occured')
# 				return

def __nop_delay(t):
	time.sleep(t * NOP_TIME)


def e_init_randb():
	global bus
	while True:
		try:
			bus = smbus.SMBus(I2C_CHANNEL)
			return
		except:
			trials+=1
			if(trials == 5):
				logger.critical('Error initializing RaB')
				sys.exit(1)

def e_randb_get_if_received():
	data = __read_data(0)
	__nop_delay(5000)
	return data

def e_randb_get_sensor():
	data = __read_data(9)
	return data

def e_randb_get_peak():
	aux1 = __read_data(7)
	aux2 = __read_data(8)
	data = (aux1 << 8) + aux2
	return data

def e_randb_get_data():
	global __data_length
	aux1 = 0
	aux2 = 0
	aux3 = 0
	if __data_length == 32:
		aux1 = __read_data(10)
	if __data_length >= 24:
		aux2 = __read_data(11)
	if __data_length >= 16:
		aux3 = __read_data(1)
	aux4 = __read_data(2)
	try:
		data = (aux1 << 24) + (aux2 << 16) + (aux3 << 8) + aux4
	except:
		data = None
	return data

def e_randb_get_range():
	aux1 = __read_data(5)
	aux2 = __read_data(6)
	data = (aux1 << 8) + aux2
	return data

def e_randb_get_bearing():
	aux1 = __read_data(3)
	aux2 = __read_data(4)
	angle = (aux1 << 8) + aux2
	return angle * 0.0001

def e_randb_reception():
	# Not yet implemented...
	raise NotImplementedError

def e_randb_send_all_data(data):
	global __data_length
	if __data_length == 32:
		__write_data(13, (data >> 24) & 0xFF)
		__write_data(19, (data >> 16) & 0xFF)
		__write_data(20, (data >>  8) & 0xFF)
	elif __data_length == 24:
		__write_data(13, (data >> 16) & 0xFF)
		__write_data(19, (data >>  8) & 0xFF)
	elif __data_length == 16:
		__write_data(13, (data >>  8) & 0xFF)
	elif __data_length == 8:
		__write_data(13, 0)
	__nop_delay(1000)
	__write_data(14, (data & 0xFF));
	__nop_delay(10000)


def e_randb_store_data(channel, data):
	global __data_length
	if __data_length == 32:
		__write_data(13, (data >> 24) & 0xFF)
		__write_data(19, (data >> 16) & 0xFF)
		__write_data(20, (data >>  8) & 0xFF)
	elif __data_length == 24:
		__write_data(13, (data >> 16) & 0xFF)
		__write_data(19, (data >>  8) & 0xFF)
	elif __data_length == 16:
		__write_data(13, (data >>  8) & 0xFF)
	elif __data_length == 8:
		__write_data(13, 0)
	__write_data(channel, (data & 0xFF))

def e_randb_send_data():
	__write_data(15, 0)
	__nop_delay(8000)

def e_randb_set_range(range):
	__write_data(12, range)
	__nop_delay(10000)

def e_randb_store_light_conditions():
	__write_data(16, 0);
	__nop_delay(150000)

def e_randb_set_calculation(type):
	__write_data(17, type)
	__nop_delay(10000)

def e_randb_get_all_data():
	# Not yet implemented...
	raise NotImplementedError

def e_randb_all_reception():
	# Not yet implemented...
	raise NotImplementedError

def e_randb_set_data_length(length):
	global __data_length
	if length == 8 or length == 16 or length == 24 or length == 32:
		__data_length = length
		__write_data(21, length)
	else:
		raise ValueError

class ERANDB(object):
	""" Set up erandb transmitter on a background thread
	The __listen() method will be started and it will run in the background
	until the application exits.
	"""
	def __init__(self, dist, tFreq = 0):
		""" Constructor
		:type dist: int
		:param dist: E-randb communication range (0=1meter; 255=0m)
		:type freq: int
		:param freq: E-randb transmit frequency (tip: 0 = no transmission; 4 = 4 per second)
		"""
		self.dist = dist
		self.__stop = True
		self.tFreq = tFreq
		self.failed = False

		 # This robot ID
		self.id = open("/boot/pi-puck_id", "r").read().strip()
		self.newIds = set()
		self.tData = self.id

		# /* Init E-RANDB board */
		e_init_randb() 
		# /* Range is tunable by software. 0 -> Full Range; 255 --> No Range
		e_randb_set_range(self.dist)
		#  * Do the calculations on the erandb board*/
		e_randb_set_calculation(ON_BOARD)
		# /* Store light conditions to improve range and bearing calculations */
		e_randb_store_light_conditions()

		logger.info('E-RANDB OK')

	def step(self):
		""" This method performs a single sequence of operations """
		if e_randb_get_if_received() != 0:
			# Get a new peer ID 
			data = e_randb_get_data()
			if data:
				newId = str(data)
				if newId != self.id: 
					self.newIds.add(newId)

		time.sleep(0.01)

		if (self.tData != None) and (self.tFreq != 0):
			if time.time()-self.__tTime > (1/self.tFreq):
				e_randb_send_all_data(int(self.tData))
				self.__tTime = time.time()

	def __listening(self):
		""" This method runs in the background until program is closed """
		self.__tTime = 0

		while True:

			try:
				self.step()
			except Exception as e:
				logger.warning(e)
				self.failed = True

			if self.__stop or self.failed:
				break 

	def start(self):
		""" This method is called to start __listening to E-Randb messages """
		if self.__stop:
			self.__stop = False

			# Initialize background daemon thread
			self.thread = threading.Thread(target=self.__listening, args=())
			self.thread.daemon = True 
			# Start the execution                         
			self.thread.start()   
		else:
			logger.warning('E-RANDB already ON')

	def stop(self):
		""" This method is called to stop the thread cleanly """   
		self.__stop = True
		self.thread.join()
		bus.close()
		logger.info('E-RANDB OFF') 

	def setData(self, tData):
		self.tData = int(tData)

	def getNew(self):
		if self.__stop:
			logger.warning('getNew: E-RANDB is OFF')

		temp = self.newIds
		self.newIds = set()
		return temp

	def hasFailed(self):
		return self.failed


if __name__ == "__main__":

    erb = ERANDB(175, 4)
    erb.start()

    while True:
    	print(erb.getNew())
    	time.sleep(0.1)
