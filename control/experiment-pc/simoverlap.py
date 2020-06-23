#!/usr/bin/env python
import matplotlib.pyplot as plt
import math
import itertools
import numpy as np
import random


# random.uniform(0, 2*math.pi)


class Robot(object):
	""" Robot which is basically a circle
	"""
	def __init__(self, x0, y0, dir0, rbRange, irRange, speed):
		""" Constructor
		:type delay: float
		:param delay: Time to wait
		"""         
		self.radius = 0.14/2
		self.irRange = irRange
		self.rbRange = rbRange
		self.x = x0
		self.y = y0
		self.v = speed
		self.dir = dir0
		self.iscontaminated = 0

	def updateState(self, timeStep, direction):
		if direction == 'straight'
			self.x += timeStep*self.v*np.cos(self.dir)
			self.y += timeStep*self.v*np.sin(self.dir)
		elif direction == 'cw'
			self.dir -= 2*timeStep*self.v/self.radius
		elif direction == 'ccw'
			self.dir += 2*timeStep*self.v/self.radius

def rotateArray(array, angle):
	R = np.array(( (np.cos(angle), -np.sin(angle)),
	               (np.sin(angle),  np.cos(angle)) ))
	v = np.array(array)

	return R.dot(v)


def getDistance(robot1, robot2):
	return math.sqrt((robot1.x-robot2.x)**2+(robot1.y-robot2.y)**2)

if __name__ == '__main__':

	results = []
	reps = 1
	for i in range(reps):

		robotList = []
		time = 0
		step = 0.1
		inRange = 0
		noRange = 0
		timeLimit = 1000
		N = 10
		arenaSizeX = 1
		arenaSizeY = 1
		contaminatedCount = 1

		# Random walk parameters
		remaining_walk_time = 3
		my_lambda = 10 # Parameter for straight movement
		turn = 4
		possible_directions = ["straight", "cw", "ccw"]
		actual_direction = "straight"

		for i in range(N):
			robotList.append(Robot(random.uniform(-arenaSizeX,arenaSizeX), random.uniform(-arenaSizeY,arenaSizeY), 0.20, 0.1))

		robotList[0].iscontaminated = 1

		while True:

			for robot in robotList:

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

				# Obstacle avoidance
				if abs(robot.x)+robot.irRange > arenaSizeX:
					robot.vx *= -1

				if abs(robot.y)+robot.irRange > arenaSizeY:
					robot.vy *= -1

				robot.updateState(step, actual_direction)

			for couple in list(itertools.combinations(robotList,2)):
				robot1 = couple[0]
				robot2 = couple[1]

				# If robots collide
				if getDistance(robot1, robot2) < (robot1.radius + robot2.radius):
					robot1.vx *= -1
					robot1.vy *= -1
					robot2.vx *= -1
					robot2.vy *= -1

				# If robots are in comms range
				if getDistance(robot1, robot2) < (robot1.erbDist + robot2.erbDist):
					# inRange += 1
					if robot1.iscontaminated and not robot2.iscontaminated:
						robot2.iscontaminated = 1
						contaminatedCount += 1
					elif robot2.iscontaminated and not robot1.iscontaminated :
						robot1.iscontaminated = 1
						contaminatedCount += 1
				else:
					pass
					# noRange += 1
			# print(contaminatedCount)
			if contaminatedCount == N:
				results.append(time)
				break

			# if time > timeLimit:
			# 	# print(inRange/noRange)
			# 	break
			else:
				time = time+step


	print(sum(results)/len(results))

