#!/usr/bin/env python
from matplotlib import pyplot as plt
from matplotlib import animation
import math
import itertools
import numpy as np
import random
from time import time
import sys

class Robot(object):
	""" Robot which is basically a circle
	"""
	def __init__(self, x0, y0, dir0, rbRange, speed):
		""" Constructor
		:type delay: float
		:param delay: Time to wait
		"""         
		self.radius = 0.070/2
		self.irRange = 0.02
		self.rbRange = rbRange
		self.x = x0
		self.y = y0
		self.v = speed
		self.dir = dir0
		self.vx = self.v*np.cos(self.dir)
		self.vy = self.v*np.sin(self.dir)
		self.iscontaminated = 0
		self.artist_body = plt.Circle((x0, y0), self.radius, color='green')
		self.artist_rb = plt.Circle((x0, y0), self.rbRange, color='blue', alpha=0.3)
		self.artist_front = plt.Circle((x0+self.radius*np.cos(self.dir), y0+self.radius*np.sin(self.dir)), 0.02, color='blue', alpha=0.3)
		self.timeToContamination = 0

		# Random walk parameters
		self.remaining_walk_time = 3
		self.my_lambda = 10 # Parameter for straight movement
		self.turn = 4
		self.possible_directions = ["straight", "cw", "ccw"]
		self.actual_direction = "straight"


	def updateState(self, timeStep, direction):
		if direction == 'straight':
			self.x += timeStep*self.vx
			self.y += timeStep*self.vy
		elif direction == 'cw':
			self.dir -= 2*timeStep*self.v/self.radius
		elif direction == 'ccw':
			self.dir += 2*timeStep*self.v/self.radius

		self.vx = self.v*np.cos(self.dir)
		self.vy = self.v*np.sin(self.dir)

		if self.iscontaminated:
			self.artist_body.set_color('red')
		else:
			self.artist_body.set_color('green')

		self.artist_body.center = (self.x, self.y)
		self.artist_rb.center = (self.x, self.y)
		self.artist_front.center = (self.x+self.radius*np.cos(self.dir), self.y+self.radius*np.sin(self.dir))

def getDistance(robot1, robot2):
	return math.sqrt((robot1.x-robot2.x)**2+(robot1.y-robot2.y)**2)


def stepAll(timeStep, robotList):
	global timeNow
	timeNow += timeStep

	for robot in robotList:

		# Obstacle avoidance in x
		if abs(robot.x)+robot.irRange+robot.radius > arenaSizeX:
			if abs(robot.x+50*timeStep*robot.vx)+robot.irRange+robot.radius > arenaSizeX:
				if robot.x < 0:
					if robot.vy > 0:
						robot.actual_direction = "cw"
					else:
						robot.actual_direction = "ccw"
				elif robot.x > 0:
					if robot.vy > 0:
						robot.actual_direction = "ccw"
					else:
						robot.actual_direction = "cw"
			else: 
				robot.actual_direction = "straight"

		# Obstacle avoidance in y
		if abs(robot.y)+robot.irRange+robot.radius > arenaSizeY:
			if abs(robot.y+50*timeStep*robot.vy)+robot.irRange+robot.radius > arenaSizeY:
				if robot.y < 0:
					if robot.vx > 0:
						robot.actual_direction = "ccw"
					else:
						robot.actual_direction = "cw"
				elif robot.y > 0:
					if robot.vx > 0:
						robot.actual_direction = "cw"
					else:
						robot.actual_direction = "ccw"
			else: 
				robot.actual_direction = "straight"

		# Random Walk
		else:		
			if (robot.remaining_walk_time == 0):
				if robot.actual_direction == "straight":
					robot.actual_direction = np.random.choice(robot.possible_directions[1:2])
					robot.remaining_walk_time = math.floor(np.random.uniform(0, 1) * robot.turn)
				else:
					robot.remaining_walk_time = math.ceil(np.random.exponential(robot.my_lambda) * 4)
					robot.actual_direction = "straight"
			else:
				robot.remaining_walk_time -= 1

		robot.updateState(timeStep, robot.actual_direction) 

	for couple in list(itertools.combinations(robotList,2)):
		robot1 = couple[0]
		robot2 = couple[1]

		# # TODO:If robots collide
		# if getDistance(robot1, robot2) < (robot1.radius + robot2.radius + robot1.irRange + robot2.irRange):

		# If robots are in comms range
		if getDistance(robot1, robot2) < (robot1.rbRange + robot2.rbRange):
			# inRange += 1
			if robot1.iscontaminated and not robot2.iscontaminated:
				robot2.iscontaminated = 1
				robot2.timeToContamination = timeNow
			elif robot2.iscontaminated and not robot1.iscontaminated:
				robot1.iscontaminated = 1
				robot1.timeToContamination = timeNow
		else:
			pass
		

def initRobots():
	robotList = []
	# Init all robots
	for i in range(N):
		x0 = random.uniform(-0.7*arenaSizeX,0.7*arenaSizeX)
		y0 = random.uniform(-0.7*arenaSizeY,0.7*arenaSizeY)
		dir0 = random.uniform(-np.pi, np.pi)
		robotList.append(Robot(x0, y0, dir0, erbDist, robotSpeed))

	robotList[0].iscontaminated = True
	return robotList


def init():
	for robot in robotList:
		ax.add_patch(robot.artist_body)
		ax.add_patch(robot.artist_rb)
		ax.add_patch(robot.artist_front)

	return [robot.artist_body for robot in robotList]+[robot.artist_rb for robot in robotList]+[robot.artist_front for robot in robotList]

def animate(i):
	global robotList, timeStep
	stepAll(timeStep,robotList)

	return [robot.artist_body for robot in robotList]+[robot.artist_rb for robot in robotList]+[robot.artist_front for robot in robotList]


arenaSizeX = 0.5
arenaSizeY = 0.5

N = 10
robotSpeed = 0.08
erbDist = 0.065
logfile = open('sim-blocktime.csv', 'w+')
timeStep = 0.1
reps = 500

if sys.argv[1] == '--ani':
	# set up figure and animation
	fig = plt.figure()
	ax = fig.add_subplot(111, aspect='equal', autoscale_on=False,
	                 xlim=(-arenaSizeX, arenaSizeX), ylim=(-arenaSizeY, arenaSizeY))
	ax.set_xticks(np.arange(-arenaSizeX,arenaSizeX+0.1,0.1))
	ax.set_yticks(np.arange(-arenaSizeY,arenaSizeY+0.1,0.1))
	ax.grid(linestyle='--')

	timeNow = 0
	robotList = initRobots()
	ani = animation.FuncAnimation(fig, animate, interval=timeStep*1000, blit=True, init_func=init)
	plt.show()

if sys.argv[1] == '--sim':

	logfile.write('{} {} {}\n'.format(' '.join(N*['Robot']),'MEAN','MAX'))
	for sim in range(reps):
		timeNow = 0
		robotList = initRobots()

		while True:
			stepAll(timeStep, robotList)
			timeNow = timeNow+timeStep
			contaminatedCount = sum([robot.iscontaminated for robot in robotList])
			if contaminatedCount == N:
				row = [round(robot.timeToContamination,2) for robot in robotList]
				logfile.write('{} {:.2f} {:.2f}\n'.format(' '.join([str(x) for x in row]), sum(row)/len(row),max(row)))
				break


