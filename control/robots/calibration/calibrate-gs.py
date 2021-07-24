#!/usr/bin/env python3
# This script obtains calibration data for the ground sensors
# Place robots randomely in an arena with binary floor data

import time
import signal
import sys
sys.path.append('..')
from randomwalk import RandomWalk
from groundsensor import GroundSensor

gsFreq = 20
rwSpeed = 500
robotID = open("/boot/pi-puck_id", "r").read().strip()

gs = GroundSensor(gsFreq)
rw = RandomWalk(rwSpeed)

rw.start()
gs.start()

calibFreq = 5
calibData = open(robotID+'.csv','w+')
calibData.write("S1 S2 S3"+"\n")
counter = 0

def STOP():
	gs.stop()
	rw.stop()
	calibData.close()

def signal_handler(sig, frame):
	STOP()

signal.signal(signal.SIGINT, signal_handler)	

while True:
	stTime = time.time()

	newValues = gs.getNew()

	calibData.write(' '.join([str(x) for x in newValues])+'\n')
	counter += 1

	if counter in [250,750,1000,1250,1500,1750]:
		print(counter)
		
	if counter == 2000:
		break
	else:
		# Read frequency @ 20 Hz.
		dfTime = time.time() - stTime
		if dfTime < (1/calibFreq):
			time.sleep((1/calibFreq) - dfTime)

STOP()

