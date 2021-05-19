#!/usr/bin/env python3
import time
import smbus
import threading
import random
import math
import numpy as np

class RandomWalk(object):
	""" Set up a Random-Walk loop on a background thread
	The __walking() method will be started and it will run in the background
	until the application exits.
	"""

	def __init__(self, MAX_SPEED):
		""" Constructor
		:type range: int
        :param enode: Random-Walk speed (tip: 500)
		"""
		self.MAX_SPEED = MAX_SPEED                          
		self.__stop = 1

	def __write_data(self, register, data):
		trials = 0
		while 1:
			try:
				self.__bus.write_word_data(self.__i2c_address, register, data)
				return
			except:
				trials+=1
				if(trials == 5):
					print('I2C write error occured')
					return
					# traceback.print_exc(file=sys.stdout)
					# sys.exit(1)

	def __read_data(self, register):
		trials = 0
		while(1):
			try:	
				return self.__bus.read_word_data(self.__i2c_address, register)
			except:
				trials+=1
				if(trials == 5):
					print('I2C read error occured')
					return
					# traceback.print_exc(file=sys.stdout)
					# sys.exit(1)			

	def __walking(self):
		""" This method runs in the background until program is closed """

		# Initialize I2C bus
		I2C_CHANNEL = 4
		EPUCK_I2C_ADDR = 0x1f
		self.__bus = smbus.SMBus(I2C_CHANNEL)
		self.__i2c_address = EPUCK_I2C_ADDR

		# Motor register addresses
		LEFT_MOTOR_SPEED = 2
		RIGHT_MOTOR_SPEED = 3

		# IR Sensors register addresses
		IR_CONTROL = 6
		IR0_REFLECTED = 7
		
		# Random walk parameters
		remaining_walk_time = 3
		my_lambda = 10 # Parameter for straight movement
		turn = 4
		possible_directions = ["straight", "cw", "ccw"]
		actual_direction = "straight"

		# Obstacle Avoidance parameters
		weights_left  = [-10, -10, -5, 0, 0, 5, 10, 10]
		weights_right = [-1 * x for x in weights_left]

		# Turn IR sensors on
		self.__write_data(IR_CONTROL, 1)

		while True:

			# Random Walk
			if (remaining_walk_time == 0):
				if actual_direction == "straight":
					actual_direction = np.random.choice(possible_directions[1:2])
					remaining_walk_time = math.floor(np.random.uniform(0, 1) * turn)
				else:
					remaining_walk_time = math.ceil(np.random.exponential(my_lambda) * 4)
					actual_direction = "straight"
			else:
				remaining_walk_time -= 1

			# Find Wheel Speed for Random-Walk
			if (actual_direction == "straight"):
				left = right = self.MAX_SPEED/2
			elif (actual_direction == "cw"):
				left  = self.MAX_SPEED/2
				right = -self.MAX_SPEED/2
			elif (actual_direction == "ccw"):
				left  = -self.MAX_SPEED/2
				right = self.MAX_SPEED/2

			# Obstacle avoidance
			self.ir = [0] * 8
			for i in range(8):
				self.ir[i] = self.__read_data(IR0_REFLECTED + i)
				if self.ir[i]>50000:
					self.ir[i] = 0
					
			# Find Wheel Speed for Obstacle Avoidance
			for i, reading in enumerate(self.ir):
				if(reading > 400):
					left  = self.MAX_SPEED/2 + weights_left[i] * reading
					right = self.MAX_SPEED/2 + weights_right[i] * reading

			# Saturate Speeds greater than MAX_SPEED
			if left > self.MAX_SPEED:
				left = self.MAX_SPEED
			elif left < -self.MAX_SPEED:
				left = -self.MAX_SPEED

			if right > self.MAX_SPEED:
				right = self.MAX_SPEED
			elif right < -self.MAX_SPEED:
				right = -self.MAX_SPEED

			# Set wheel speeds
			self.__write_data(LEFT_MOTOR_SPEED, int(left))
			self.__write_data(RIGHT_MOTOR_SPEED, int(right))

			if self.__stop:
				# Stop IR and Motor
				self.__write_data(IR_CONTROL, 0) 
				self.__write_data(LEFT_MOTOR_SPEED, 0) 
				self.__write_data(RIGHT_MOTOR_SPEED, 0)
				self.setLEDs(0b00000000) 
				self.bus.close()
				break 
			else:
				time.sleep(0.1)

	def start(self):
		""" This method is called to start __walking """
		if self.__stop:
			self.__stop = 0
			# Initialize background daemon thread
			thread = threading.Thread(target=self.__walking, args=())
			thread.daemon = True 

			# Start the execution                         
			thread.start()   
		else:
			print('Already Walking')

	def stop(self):
		""" This method is called before a clean exit """
		self.__stop = 1
		print('Random-Walk OFF') 

	def setLEDs(self, state):
		""" This method is called set the outer LEDs to an 8-bit state """
		OUTER_LEDS = 0
		self.__write_data(OUTER_LEDS, state)

			
	def flashLEDs(self, delay = 0.1):
		self.setLEDs(0b11111111)
		time.sleep(delay)
		self.setLEDs(0b00000000)

	def getIr(self):
		""" This method returns the IR readings """
		return self.ir







	
