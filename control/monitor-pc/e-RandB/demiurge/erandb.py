#
# e-puck Range and Bearing Board library, adapted from e-puck dsPIC library
# See https://www.gctronic.com/doc/index.php/Others_Extensions
# Modified for DEMIURGE firmware (https://github.com/demiurge-project/argos3-epuck/tree/master/erab_firmware)
#

import time
import smbus
import sys
import traceback

I2C_CHANNEL = 12
LEGACY_I2C_CHANNEL = 4
RANDB_I2C_ADDR = 0x20

ON_BOARD = 0
ON_ROBOT = 1

NOP_TIME = 0.000001


__bus = None
__data_length = 16


def __write_data(addr, data):
	trials = 0
	while 1:
		try:
			__bus.write_byte_data(RANDB_I2C_ADDR, addr, data)
			return
		except:
			trials+=1
			if(trials == 10):
				prpint('I2C write error occured')
				print('Max trials:', trials, 'reached.')
				traceback.print_exc(file=sys.stdout)
				sys.exit(1)

def __read_data(addr):
	trials = 0
	while 1:
		try:
			return __bus.read_byte_data(RANDB_I2C_ADDR, addr)
		except:
			trials+=1
			if(trials == 10):
				prpint('I2C read error occured')
				print('Max trials:', trials, 'reached.')
				traceback.print_exc(file=sys.stdout)
				sys.exit(1)

def __nop_delay(t):
	time.sleep(t * NOP_TIME)


def e_init_randb():
	global __bus
	try:
		__bus = smbus.SMBus(I2C_CHANNEL)
	except FileNotFoundError:
		__bus = smbus.SMBus(LEGACY_I2C_CHANNEL)

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
	data = (aux1 << 24) + (aux2 << 16) + (aux3 << 8) + aux4
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
	# Not yet implemented...
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
	__write_data(14, (data & 0xFF))
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
	__write_data(16, 0)
	__nop_delay(150000)

def e_randb_set_calculation(type):
	__write_data(17, type)
	__nop_delay(10000)

def e_randb_get_all_data():
	# Not yet implemented...
	raise NotImplementedError

def e_randb_all_reception():
	# Not yet implemented...
	raise NotImplementedError

def e_randb_set_data_length(length):
	global __data_length
	if length == 8 or length == 16 or length == 24 or length == 32:
		__data_length = length
		__write_data(21, length)
	else:
		raise ValueError
