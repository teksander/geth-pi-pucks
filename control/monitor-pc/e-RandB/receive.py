#!/usr/bin/env python3

#
# e-puck Range and Bearing Board example, adapted from e-puck dsPIC 'randbReceiver'
# See https://www.gctronic.com/doc/index.php/Others_Extensions
#

import time
from erandb import *
import math

print('e-puck range and bearing board receive test')

print('Initialising RandB board...')

# /* Init E-RANDB board */
e_init_randb()

# Range is tunable by software. 
# 0 -> Full Range (1m. approx depending on light conditions)
# 255 -> No Range (0cm. approx, depending on light conditions)
e_randb_set_range(150)

# At some point we thought that the board could just take
# data and leave the calculations for the robot.
# At the moment, it is better to allow the board to do the calculations
e_randb_set_calculation(ON_BOARD)

# Store light conditions to use them as offset for the calculation 
# of the range and bearing
e_randb_store_light_conditions()

print('Receiving...')

while True:
	if e_randb_get_if_received() != 0:
		# Get data
		data = e_randb_get_data()
		# Get bearing
		bear = e_randb_get_bearing()
		# Get range
		rang = e_randb_get_range()
		# Print data received
		print("Received:", data, (bear*180/math.pi), rang)
