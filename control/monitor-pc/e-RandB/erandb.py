#
# e-puck Range and Bearing Board library, adapted from e-puck dsPIC library
# See https://www.gctronic.com/doc/index.php/Others_Extensions
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


def __write_data(addr, data):
	trials = 0
	while 1:
		try:
			__bus.write_byte_data(RANDB_I2C_ADDR, addr, data)
			return
		except:
			trials+=1
			print('I2C failed. Trials=', trials)
			if(trials == 10):
				print('I2C write error occured')
				traceback.print_exc(file=sys.stdout)
				sys.exit(1)

def __read_data(addr):
	trials = 0
	while 1:
		try:
			return __bus.read_byte_data(RANDB_I2C_ADDR, addr)
		except:
			trials+=1
			print('I2C failed. Trials=', trials)
			if(trials == 10):
				print('I2C read error occured')
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
	aux1 = __read_data(1)
	aux2 = __read_data(2)
	data = (aux1 << 8) + aux2
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
	__write_data(13, (data >> 8) & 0xFF)
	__nop_delay(1000)
	__write_data(14, (data & 0xFF))
	__nop_delay(10000)

def e_randb_store_data(channel, data):
	__write_data(13, (data >> 8) & 0xFF)
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
