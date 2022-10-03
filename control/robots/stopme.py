#!/usr/bin/env python3
# This script obtains calibration data for the ground sensors
# Place robots randomely in an arena with binary floor data

import time
import signal
import sys
sys.path.append('..')
from randomwalk import RandomWalk
from groundsensor import GroundSensor

gsFreq = 0
rwSpeed = 0
robotID = open("/boot/pi-puck_id", "r").read().strip()

gs = GroundSensor(gsFreq)
rw = RandomWalk(rwSpeed)

rw.start()
gs.start()

def STOP():
	gs.stop()
	rw.stop()
	calibData.close()

def signal_handler(sig, frame):
	STOP()

signal.signal(signal.SIGINT, signal_handler)	


STOP()

