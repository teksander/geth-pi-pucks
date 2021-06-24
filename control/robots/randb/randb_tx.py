from smbus import SMBus
import sys
import time
import struct

I2C_CHANNEL = 4
RANDB_ADDR = 0x20

bus = None
rab_state = 0

def write_reg(reg, data):
	global bus 
	trials = 0
	
	while trials < 25:
		try:
			bus.write_i2c_block_data(RANDB_ADDR, reg, data)
		except:
			trials += 1
			print('Write Error. Trial #:', trials)
			continue
		break
		
	if trials == 25:
		print("write error")
		return -1
	
	return 0
		
def read_reg(reg, count):
	global bus
	trials = 0
	data = None
	
	while trials < 25:
		try:			
			data = bus.read_i2c_block_data(RANDB_ADDR, reg, count)
			#print(data)
		except:
			trials += 1
			print('Read Error. Trial #:', trials)
			continue
		break
	
	if trials == 25:
		print("read error")
		return None
	
	return data;

	
try:
	bus = SMBus(I2C_CHANNEL)
except:
	sys.exit(1)


while 1:
	start = time.time()

	if(rab_state == 0):
		write_reg(12, [200]) # Set range.
		write_reg(17, [0]) # Onboard calculation.
		rab_state = 1		
	elif(rab_state == 1):
		write_reg(13, [0xAA])
		write_reg(14, [0xFF])

	# Communication frequency @ 20 Hz.
	time_diff = time.time() - start
	if time_diff < 0.050:
		time.sleep(0.050 - time_diff);
