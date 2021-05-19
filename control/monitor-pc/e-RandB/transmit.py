#!/usr/bin/env python3

#
# e-puck Range and Bearing Board example, adapted from e-puck dsPIC 'randbEmitter'
# See https://www.gctronic.com/doc/index.php/Others_Extensions
#

import time
from erandb import *

print('e-puck range and bearing board transmit test')

print('Initialising RandB board...')

# /* Init E-RANDB board */
e_init_randb()

# Range is tunable by software. 
# 0 -> Full Range (1m. approx depending on light conditions)
# 255 -> No Range (0cm. approx, depending on light conditions)
e_randb_set_range(0)

# At some point we thought that the board could just take
# data and leave the calculations for the robot.
# At the moment, it is better to allow the board to do the calculations
e_randb_set_calculation(ON_BOARD)

# Store light conditions to use them as offset for the calculation 
# of the range and bearing
e_randb_store_light_conditions()

print('Transmitting...')

# The counter for sending
data = 0

while True:
	# Send the data in one sensor
	e_randb_store_data(0, data)
	e_randb_send_data()
	print("Sent:", data)
	# Increase data
	data += 1
	# Data to be sent must be lower than 16 bits
	if data == 65535:
		data = 0
	time.sleep(1.0)
