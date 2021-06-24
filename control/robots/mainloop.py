#!/usr/bin/env python3
# This is the main control loop running on the foreground in each robot
# Optional flags:
# --byz       (starts experiment as a byzantine robot)
# --sandbox   (control sensors and actuators without starting experiment)
# --synctime  (synchronizes clocks and enters sandbox)
# --peer2pc   (peers to the computer and enters sandbox)
# --nowalk    (normal experiment but robots don't move)

import time
import sys
import signal
import threading
import subprocess
import random
from console import init_web3, registerSC
from erandb import ERANDB
from randomwalk import RandomWalk
from groundsensor import GroundSensor
from rgbleds import RGBLEDs
from aux import *
import logging

global startFlag
global isbyz
global gasLimit
global gasprice
global gas
gasLimit = 0x9000000
gasprice = 0x900000
gas = 0x90000
startFlag = 0
isbyz = 0

# /* Experiment Parameters */
#######################################################################
loglevel = 40
tcpPort = 40421 
erbDist = 200
erbtFreq = 10
gsFreq = 20
rwSpeed = 500
pcID = '100'

estimateRate = 1
voteRate = 45 
bufferRate = 0.25
eventRate = 1
globalPeers = 0
ageLimit = 2

# Global parameters
# subprocess.call("source ../../globalconfig")

# /* Initialize Logging Files and Console Logging*/
#######################################################################

# Experimental logs (recorded to file)
header = ['EVENT DESCRIPTION']
mainlog = Logger('logs/main.txt', header)

header = ['ESTIMATE','W','B','S1','S2','S3']
estimatelog = Logger('logs/estimate.csv', header)

header = ['#BUFFER', '#GETH','#ALLOWED', 'BUFFERPEERS', 'GETHPEERS','ALLOWED']
bufferlog = Logger('logs/buffer.csv', header, 1)

header = ['VOTE']
votelog = Logger('logs/vote.csv', header)

header = ['TELAPSED','TIMESTAMP','BLOCK', 'HASH', 'PHASH', 'DIFF', 'TDIFF', 'SIZE','TXS', 'UNC']
blocklog = Logger('logs/block.csv', header)

header = ['BLOCK', 'BALANCE', 'UBI', 'PAY','#ROBOT', 'MEAN', '#VOTES','#OKVOTES', 'R?','C?']
sclog = Logger('logs/sc.csv', header)

header = ['#BLOCKS']
synclog = Logger('logs/sync.csv', header)

header = ['CHAINDATASIZE', '%CPU']
extralog = Logger('logs/extra.csv', header)

# Console logs (Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL)
logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
# File logs (Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL)
# fh.setLevel(fileloglevel)

# Sublogs
mainlogger = logging.getLogger('main')
estimatelogger = logging.getLogger('estimate')
bufferlogger = logging.getLogger('buffer')
eventlogger = logging.getLogger('events')
votelogger = logging.getLogger('voting')

# List of logmodules --> iterate .start() to start all; remove from list to not log
logmodules = [bufferlog, estimatelog, votelog, sclog, mainlog, blocklog, synclog, extralog]

# List of logmodules --> specify submodule loglevel if desired
logging.getLogger('main').setLevel(loglevel)
logging.getLogger('estimate').setLevel(loglevel)
logging.getLogger('buffer').setLevel(50)
logging.getLogger('events').setLevel(loglevel)
logging.getLogger('voting').setLevel(10)
logging.getLogger('console').setLevel(loglevel)
logging.getLogger('erandb').setLevel(10)
logging.getLogger('randomwalk').setLevel(loglevel)
logging.getLogger('groundsensor').setLevel(loglevel)
logging.getLogger('aux').setLevel(loglevel)
logging.getLogger('rgbleds').setLevel(loglevel)

# /* Initialize Sub-modules */
#######################################################################

# /* Init web3.py */
mainlogger.info('Initialising Python Geth Console...')
w3 = init_web3()

# /* Init an instance of peer for this Pi-Puck */
myID  = open("/boot/pi-puck_id", "r").read().strip()
myEN  = w3.geth.admin.nodeInfo().enode
myKEY = w3.eth.coinbase

me = Peer(myID, myEN, myKEY)
# /* Init an instance of peer for the monitor PC */
pc = Peer(pcID)

# /* Init an instance of the buffer for peers  */
mainlogger.info('Initialising peer buffer...')
pb = PeerBuffer(ageLimit)

# /* Init TCP server, __hosting process and request function */
mainlogger.info('Initialising TCP server...')
tcp = TCP_server(me.enode, me.ip, tcpPort)

# /* Init E-RANDB __listening process and transmit function
mainlogger.info('Initialising RandB board...')
erb = ERANDB(erbDist, erbtFreq)

# /* Init Ground-Sensors, __mapping process and vote function */
mainlogger.info('Initialising ground-sensors...')
gs = GroundSensor(gsFreq)

# /* Init Random-Walk, __walking process */
mainlogger.info('Initialising random-walk...')
rw = RandomWalk(rwSpeed)

# /* Init LEDs */
rgb = RGBLEDs()

# List of submodules --> iterate .start() to start all
submodules = [w3.geth.miner, tcp, erb, gs, rw]

# /* Define Main-modules */
#######################################################################
# The 4 Main-modules: 
# "Estimate"  Rate 1Hz)  queries groundsensor and generates a robot estimate (opinion)
# "Buffer"    (Rate 1Hz) queries RandB to get neighbor identities and add/remove on Geth
# "Vote"   (Rate 1/45Hz) communicate with geth to send votes every 45s
# "Event"  (Every block) when a new block is detected make blockchain queries/sends/log block data 

def Estimate(rate = estimateRate):
	""" Control routine to update the local estimate of the robot """
	global estimate
	estimate = 0
	totalWhite = 0
	totalBlack = 0

	while True:
		if not startFlag:
			mainlogger.info('Stopped Estimating')
			break
		else:
			tic = TicToc(rate, 'Estimate')

		# Set counters for grid colors
		newValues = gs.getAvg()

		if gs.hasFailed():
			gs.stop()
			time.sleep(1)
			gs.start()
			estimatelog.log([None]) 

		elif newValues == None:
			estimatelog.log([None]) 
		else:
			for value in newValues:
				if value > 700:
					totalWhite += 1
					# rw.setLEDs(0b11111111)
				else:
					totalBlack += 1
					# rw.setLEDs(0b00000000)
			if isbyz:
				estimate = 0
			else:
				estimate = (0.5+totalWhite)/(totalWhite+totalBlack+1)

			estimatelog.log([round(estimate,3),totalWhite,totalBlack,newValues[0],newValues[1],newValues[2]]) 

		tic.toc()

def Buffer(rate = bufferRate, ageLimit = ageLimit):
	""" Control routine for robot-to-robot dynamic peering """
	
	def globalBuffer():
		peerFile = open('pi-pucks.txt', 'r') 
		tcp.unlock()

		for newId in peerFile:
			newId = newId.strip()
			pb.addPeer(newId)

		for peer in pb.buffer: 
			try:
				peer.enode = tcp.request(newPeer.ip, tcp.port)
				w3.geth.admin.addPeer(peer.enode)
				bufferlogger.debug('Peered to %s', peer.id)
			except:
				bufferlogger.debug('Failed to peer to %s', peer.id)

		peerFile.close()

	# def localBufferbkup():
	# 	# Collect new peer IDs from E-RANDB to the buffer
	# 	for newId in erb.getNew():
	# 		tcp.allow(newId)
	# 		pb.addPeer(newId)

	# 	# If there are no peers in buffer; turn off LEDs
	# 	if not pb.buffer:
	# 		rw.setLEDs(0b00000000)
	# 		pass

	# 	# If there are peers in buffer; perform buffering tasks for each peer
	# 	else:
	# 		for peer in pb.buffer:

	# 			# If the peer has aged out: Remove from buffer and continue to next peer
	# 			if peer.isDead:
	# 				if peer.enode:
	# 					w3.provider.make_request("admin_removePeer",[peer.enode])
	# 				tcp.unallow(peer.id)
	# 				pb.removePeer(peer.id)
	# 				mainlog.log(['Killed peer {} @ age {:.1f}'.format(peer.id, peer.age)])
	# 				bufferlogger.debug('Killed peer %s @ age %.2f', peer.id, peer.age)
	# 				continue

	# 			# If the enode is unknown: Query enode and add to Geth. If fail, continue
	# 			elif not peer.enode and peer.timeout<=0:

	# 				if peer.id in enodesDict:
	# 					peer.enode = enodesDict[peer.id]
	# 					bufferlogger.debug('Got enode from dict')
	# 				else:
	# 					try:
	# 						peer.enode = tcp.request(peer.ip, tcp.port)
	# 						peer.trials = 0
	# 						enodesDict[peer.id] = peer.enode
	# 						bufferlogger.debug('Requested enode')   		 
	# 					except:
	# 						peer.trials += 1
	# 						if peer.trials == 5: 
	# 							peer.setTimeout()
	# 							mainlog.log(['Timing out peer {}'.format(peer.id)])
	# 							bufferlogger.debug('Timing out peer %s', peer.id)
	# 						continue

	# 				if int(me.id) > int(peer.id):
	# 					w3.geth.admin.addPeer(peer.enode)  
	# 					bufferlogger.debug('I am adding peer %s', peer.id)
	# 				else:
	# 					bufferlogger.debug('I am being added by peer %s', peer.id)
	# 					rw.setLEDs(0b11111111)
	def localBuffer():
		pb.aging()
		gethEnodes = getEnodes()
		gethIds = getIds(gethEnodes)

		# If there are peers in buffer; perform buffering tasks for each peer
		for peer in pb.buffer:
			if peer.isDead:
				tcp.unallow(peer.id)
				pb.removePeer(peer.id)
				bufferlogger.debug('Killed peer %s @ age %.2f', peer.id, peer.age)
				if peer.id in gethIds:
					getEnodeById(peer.id, gethEnodes)
					w3.provider.make_request("admin_removePeer",[peer.enode])
					gethIds.remove(peer.id)
					bufferlogger.debug('Removed peer %s @ age %.2f', peer.id, peer.age)
				continue

			elif int(me.id) > int(peer.id):
				# IWf the enode is unknown: Query enode and add to Geth. If fail, continue
				if not peer.enode and peer.timeout<=0:
					try:
						peer.enode = tcp.request(peer.ip, tcp.port)
						bufferlogger.debug('Requested enode')   		 
					except:
						peer.trials += 1
						if peer.trials == 5: 
							peer.setTimeout()
							bufferlogger.debug('Timing out peer %s', peer.id)
						continue

					if peer.id not in gethIds:
						w3.geth.admin.addPeer(peer.enode)  
						bufferlogger.debug('Added peer %s @ age %.2f', peer.id, peer.age)

		# Turn on LEDs accordingly
		nPeers = len(gethIds)
		if nPeers >= 2:
			rw.setLEDs(0b11111111)
		elif nPeers == 1:
			rw.setLEDs(0b01010101)
		elif nPeers == 0:
			rw.setLEDs(0b00000000)

		# Collect new peer IDs from E-RANDB to the buffer
		erbIds = erb.getNew()
		pb.addPeer(erbIds)
		tcp.allow(erbIds)	

		if len([pb.getIds]) > 6:
			bufferlogger.critical('Woooaaahh too many peers. Killing all for safety')
			for peer in pb.buffer:
				peer.kill()
				

		if bufferlog.isReady():
			# for enode in gethEnodes
			# 	if not in pb.getEnodes():
			# 		w3.provider.make_request("admin_removePeer",[peer.enode])
			# 		bufferlogger.debug('Killed peer %s @ age %.2f', peer.id, peer.age)
			bufferlog.log([len(gethIds), len(erbIds), len(tcp.allowed), ';'.join(erbIds), ';'.join(gethIds), ';'.join(tcp.allowed)])
		

	while True:
		if not startFlag:
			mainlogger.info('Stopped Buffering')
			break

		tic = TicToc(rate, 'Buffer')
				
		if globalPeers:
			globalBuffer()
			break
		else:
			localBuffer()

		tic.toc()
	
def Vote(rate = voteRate):
	""" Control routine to broadcast current estimate to the blockchain """
	ticketPrice = sc.functions.getTicketPrice().call()
	myVoteCounter = 0
	myOkVoteCounter = 0
	time.sleep(rate)
	while True:
		if not startFlag:
			mainlogger.info('Stopped Voting')
			break

		tic = TicToc(rate, 'Vote')


		while True:
			balance = getBalance()

			if balance < 40.05:
				myVoteCounter += 1
				mainlog.log(['Cannot Vote (No Balance). Balance: {}'.format(balance)])
				votelog.log([None])
				votelogger.debug('Cannot vote: (%i/%i) (No balance)', myOkVoteCounter, myVoteCounter)
				rgb.flashRed()
				break
			else:
				try:
					vote = int(estimate*1e7)
					voteHash = sc.functions.sendVote(vote).transact({'from': me.key,'value': w3.toWei(ticketPrice,'ether'), 'gas':gasLimit, 'gasPrice':gasprice})
					voteReceipt = w3.eth.waitForTransactionReceipt(voteHash, timeout=120)

					mainlog.log(['Voted: {}; Status: {}'.format(estimate, voteReceipt.status)])
					votelog.log([vote])
					myVoteCounter += 1
					myOkVoteCounter += 1
					votelogger.debug('Voted successfully: %.2f (%i/%i)', estimate, myOkVoteCounter, myVoteCounter)
					rgb.flashGreen()
					break

					if voteReceipt.status == 0:
						print(voteReceipt)

				except ValueError:
					mainlog.log(['Failed Vote (ValueError). Balance: {}'.format(balance)])
					votelog.log([None])
					votelogger.debug('Failed to vote: (%i/%i) (No balance)', myOkVoteCounter, myVoteCounter)
					rgb.flashRed()
					break

				except:
					mainlog.log(['Failed Vote (Unexpected). Trying again. Balance: {}'.format(balance)])
					votelogger.error('Failed to vote: (Unexpected)')

		# Low frequency logging of chaindata size and cpu usage
		chainSize = getFolderSize('/home/pi/geth-pi-pucks/geth')
		cpuPercent= getCPUPercent()
		extralog.log([chainSize,cpuPercent])

		tic.toc()

def Event(rate = eventRate):
	""" Control routine to perform tasks triggered by an event """

    # sc.events.your_event_name.createFilter(fromBlock=block, toBlock=block, argument_filters={"arg1": "value"}, topics=[])
	blockFilter = w3.eth.filter('latest')
	def blockHandle():
		""" Tasks when a new block is added to the chain """
		global ubi, payout, newRound
		# 1) Log relevant block details 
		block = w3.eth.getBlock(blockHex)
		blocklog.log([time.time()-block.timestamp, round(block.timestamp-blocklog.tStart, 3), block.number, block.hash.hex(), block.parentHash.hex(), block.difficulty, block.totalDifficulty, block.size, len(block.transactions), len(block.uncles)])

		# 2) Log relevant smart contract details
		balance = getBalance()
		payout = sc.functions.askForPayout().call({'gas':gasLimit})
		ubi = sc.functions.askForUBI().call({'gas':gasLimit})
		robotCount = sc.functions.getRobotCount().call()
		mean = sc.functions.getMean().call()
		voteCount = sc.functions.getVoteCount().call()
		voteOkCount = sc.functions.getVoteOkCount().call()
		newRound = sc.functions.isNewRound().call()
		consensus = sc.functions.isConverged().call()

		sclog.log([block.number, balance, ubi, payout, robotCount, mean, voteCount, voteOkCount, newRound, consensus])

		rgb.flashWhite(0.2)

		if consensus == 1:
			rgb.setLED(rgb.all, [rgb.green]*3)
			rgb.freeze()

	while True:
		if not startFlag:
			mainlogger.info('Stopped Events')
			break

		tic = TicToc(rate, 'Event')

		newBlocks = blockFilter.get_new_entries()
		if newBlocks:
			synclog.log([len(newBlocks)])

			for blockHex in newBlocks:
				blockHandle()

			if ubi != 0:
				sc.functions.askForUBI().transact({'gas':gasLimit})
				eventlogger.debug('Asked for UBI')

			if payout != 0:
				sc.functions.askForPayout().transact({'gas':gasLimit})
				eventlogger.debug('Asked for payout')

			if newRound:
				try:
					sc.functions.updateMean().transact({'gas':gasLimit})
					eventlogger.debug('Updated mean')
				except:
					eventlogger.debug('Failed to update mean')
		tic.toc()

# /* Initialize background daemon threads for the Main-Modules*/
#######################################################################

estimateTh = threading.Thread(target=Estimate, args=())
estimateTh.daemon = True   

bufferTh = threading.Thread(target=Buffer, args=())
bufferTh.daemon = True    

voteTh = threading.Thread(target=Vote, args=())
voteTh.daemon = True                        

eventTh = threading.Thread(target=Event, args=())
eventTh.daemon = True                        

mainmodules = [estimateTh, bufferTh, voteTh, eventTh]


def START(modules = submodules + mainmodules, logs = logmodules):
	mainlogger.info('Starting Experiment')
	global startFlag
	for log in logs:
		try:
			log.start()
		except:
			mainlogger.critical('Error Starting Log')

	startFlag = 1 
	for module in modules:
		try:
			module.start()
		except:
			mainlogger.critical('Error Starting Module')

	mainlog.log(['STARTED EXPERIMENT'])

def signal_handler(sig, frame):

	def STOP(modules = submodules, logs = logmodules):
		mainlogger.info('Ctrl+C pressed. Stopping...')
		global startFlag

		mainlog.log(['STOPPED EXPERIMENT'])
		mainlogger.info('--/-- Stopping Main-modules --/--')
		startFlag = 0
		time.sleep(1.5)

		mainlogger.info('--/-- Stopping Sub-modules --/--')
		for submodule in modules:
			try:
				submodule.stop()
			except:
				mainlogger.warning('Error stopping submodule')

		for log in logs:
			try:
				log.close()
			except:
				mainlogger.warning('Error Closing Logfile')
				
		if isbyz:
			pass
			mainlogger.info('This Robot was BYZANTINE')

	if not startFlag:
		mainlogger.info('Experiment has not started. Exiting')
		sys.exit()
	elif startFlag:
		STOP()


signal.signal(signal.SIGINT, signal_handler)	

# /* Some useful functions */
#######################################################################

def getBalance():
	return round(w3.fromWei(w3.eth.getBalance(me.key), 'ether'), 2)

def getDiff():
	return set(getEnodes())-set(pb.getEnodes())-{me.enode}

def getEnodes():
    return [peer.enode for peer in w3.geth.admin.peers()]

def getEnodeById(__id, gethEnodes = None):
    if not gethEnodes:
        gethEnodes = getEnodes() 
    for enode in gethEnodes:
        if readEnode(enode, output = 'id') == __id:
            return enode


def getIds(__enodes = None):
    if __enodes:
        return [enode.split('@',2)[1].split(':',2)[0].split('.')[-1] for enode in __enodes]
    else:
        return [enode.split('@',2)[1].split(':',2)[0].split('.')[-1] for enode in getEnodes()]

def getIps():
    return [enode.split('@',2)[1].split(':',2)[0] for enode in getEnodes()]

def waitForTS():
	while True:
		try:
			TIME = tcp.request(pc.ip, 40123)
			subprocess.call(["sudo","timedatectl","set-time",TIME])
			mainlog.log(['SETUP: Synced Time'])
			mainlogger.info('Synced Time')
			break
		except:
			time.sleep(1)

def waitForPC():
	while True:
		try:
			pc.enode = tcp.request(pc.ip, tcpPort)
			pc.key = tcp.request(pc.ip, 40422)
			w3.geth.admin.addPeer(pc.enode)
			mainlog.log(['SETUP: Peered to PC'])
			mainlogger.info('Peered to PC')
			break
		except:
			time.sleep(1)

# /* BEGIN EXPERIMENT */ 
#######################################################################

if len(sys.argv) == 1:
	#######################################################################

	# /* Wait for Time Synchronization */ 
	mainlogger.info('Waiting for Time Sync...')
	waitForTS()

	# /* Register robot to the Smart Contract*/
	sc = registerSC(w3)
	sc.functions.registerRobot().transact({'gas':gasLimit, 'gasPrice':gasprice})

	input("Press Enter to start experiment")
	START()
	mainlogger.info('Type Ctrl+C to stop experiment')
	mainlogger.info('Robot ID: %s', me.id)


elif len(sys.argv) == 2:
	if sys.argv[1] == '--byz':

		# /* Wait for Time Synchronization */ 
		mainlogger.info('Waiting for Time Sync...')
		waitForTS()

		# /* Register robot to the Smart Contract*/
		sc = registerSC(w3)
		sc.functions.registerRobot().transact({'gas':gasLimit, 'gasPrice':gasprice})

		input("Press Enter to start experiment")
		isbyz = 1
		START()
		mainlogger.info('Type Ctrl+C to stop experiment')
		mainlogger.info('Robot ID: %s (Byzantine)', me.id)

	if sys.argv[1] == '--nowalk':

		# /* Wait for Time Synchronization */ 
		mainlogger.info('Waiting for Time Sync...')
		waitForTS()

		# /* Register robot to the Smart Contract*/
		sc = registerSC(w3)
		sc.functions.registerRobot().transact({'gas':gasLimit, 'gasPrice':gasprice})

		input("Press Enter to start experiment")
		rw.setWalk(False)
		START()
		mainlogger.info('Type Ctrl+C to stop experiment')
		mainlogger.info('Robot ID: %s', me.id)

	# Alternative start executions
	elif sys.argv[1] == '--sandbox':
		print('---//--- SANDBOX-MODE ---//---')		
		startFlag = 1	

	elif sys.argv[1] == '--synctime':
		print('---//--- SYNC-TIME ---//---')
		# /* Wait for Time Synchronization */ 
		waitForTS()
		startFlag = 1

	elif sys.argv[1] == '--peer2pc':
		print('---//--- PEER-PC ---//---')
		# /* Wait for PC Enode */
		waitForPC()
		startFlag = 1	