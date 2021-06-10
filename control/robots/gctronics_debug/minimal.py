import time
from erandb import ERANDB
from randomwalk import RandomWalk
from rgbleds import RGBLEDs
from groundsensor import GroundSensor

id = open("/boot/pi-puck_id", "r").read().strip()

print('Initialising E-RANDB board...')
erb = ERANDB(100)

print('Initialising Random-Walk...')
rw = RandomWalk(500)

print('Initialising Ground-Sensors...')
gs = GroundSensor(100)

# /* Init LEDs */
rgb = RGBLEDs()

erb.start()
rw.start()
gs.start()

counts = 0
newValues = 0
while 1:
	erb.transmit(id)
	for newId in erb.getNew():
		counts += 1
		#print(str(newId))
		print(newValues)
	
	rgb.setLED(rgb.all, [rgb.green]*3)
	rw.setLEDs(0b00000000)
	time.sleep(0.1)
	rgb.setLED(rgb.all, [0]*3)
	rw.setLEDs(0b11111111)
	time.sleep(0.1)
	
	newValues = gs.getAvg()
	if gs.hasFailed():
		gs.stop()
		time.sleep(1)
		gs.start()	
	