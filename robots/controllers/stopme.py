#!/usr/bin/env python3

import time, signal
from randomwalk import RandomWalk
from groundsensor import GroundSensor
from rgbleds import RGBLEDs

gsFreq = 0
rwSpeed = 0
robotID = open("/boot/pi-puck_id", "r").read().strip()

gs = GroundSensor(gsFreq)
rw = RandomWalk(rwSpeed)
rgb = RGBLEDs()

rw.start()
gs.start()

def STOP():
	gs.stop()
	rw.stop()
	rgb.stop()

def signal_handler(sig, frame):
	STOP()

signal.signal(signal.SIGINT, signal_handler)	

STOP()

