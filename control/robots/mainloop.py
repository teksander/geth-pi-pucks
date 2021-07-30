#!/usr/bin/env python3
# This is the main control loop running in each robot
# Optional flags:
# --byz       (starts experiment as a byzantine robot)
# --sandbox   (control sensors and actuators without starting experiment)
# --synctime  (synchronizes clocks and enters sandbox)
# --peer2pc   (peers to the computer and enters sandbox)
# --nowalk    (normal experiment but robots don't move)

# /* Logging Levels for Console and File */
#######################################################################
loglevel = 30
logtofile = False 

# /* Experiment Parameters */
#######################################################################
tcpPort = 40421 
erbDist = 175
erbtFreq = 10
gsFreq = 20
rwSpeed = 500
pcID = '100'

estimateRate = 1
voteRate = 45 
bufferRate = 0.33
eventRate = 1
globalPeers = 0
ageLimit = 2

timeLimit = 1800

# /* Global Variables */
#######################################################################
global startFlag, isByz
startFlag = False
isByz = False

global gasLimit, gasprice, gas
gasLimit = 0x9000000
gasprice = 0x900000
gas = 0x90000

global txList, startTime
txList = []

# /* Import Packages */
#######################################################################
import logging
if logtofile:
	logFile = 'logs/loggers.txt'
	logging.basicConfig(filename=logFile, filemode='w+', format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
else:
	logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
import time
import sys
import os
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

# Global parameters
# subprocess.call("source ../../globalconfig")

# Calibrated parameters
with open('calibration/gsThreshes.txt') as calibFile:
	gsThresh = list(map(int, calibFile.readline().split()))

# /* Initialize Logging Files and Console Logging*/
#######################################################################

robotID = open("/boot/pi-puck_id", "r").read().strip()

# Experiment data logs (recorded to file)
header = ['ESTIMATE','W','B','S1','S2','S3']
estimatelog = Logger('logs/estimate.csv', header, 10)
header = ['#BUFFER', '#GETH','#ALLOWED', 'BUFFERPEERS', 'GETHPEERS','ALLOWED']
bufferlog = Logger('logs/buffer.csv', header, 2)
header = ['VOTE']
votelog = Logger('logs/vote.csv', header)
header = ['TELAPSED','TIMESTAMP','BLOCK', 'HASH', 'PHASH', 'DIFF', 'TDIFF', 'SIZE','TXS', 'UNC', 'PENDING', 'QUEUED']
blocklog = Logger('logs/block.csv', header)
header = ['BLOCK', 'BALANCE', 'UBI', 'PAY','#ROBOT', 'MEAN', '#VOTES','#OKVOTES', '#MYVOTES','#MYOKVOTES', 'R?','C?']
sclog = Logger('logs/sc.csv', header)
header = ['#BLOCKS']
synclog = Logger('logs/sync.csv', header)
header = ['CHAINDATASIZE', '%CPU']
extralog = Logger('logs/extra.csv', header, 5)
header = ['MINED?', 'BLOCK', 'NONCE', 'VALUE', 'STATUS', 'HASH']
txlog = Logger('logs/tx.csv', header)

# List of logmodules --> iterate .start() to start all; remove from list to ignore
logmodules = [bufferlog, estimatelog, votelog, sclog, blocklog, synclog, extralog]

# Console/file logs (Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL)
mainlogger = logging.getLogger('main')
estimatelogger = logging.getLogger('estimate')
bufferlogger = logging.getLogger('buffer')
eventlogger = logging.getLogger('events')
votelogger = logging.getLogger('voting')

# List of logmodules --> specify submodule loglevel if desired
logging.getLogger('main').setLevel(loglevel)
logging.getLogger('estimate').setLevel(loglevel)
logging.getLogger('buffer').setLevel(50)
logging.getLogger('events').setLevel(loglevel)
logging.getLogger('voting').setLevel(loglevel)
logging.getLogger('console').setLevel(loglevel)
logging.getLogger('erandb').setLevel(10)
logging.getLogger('randomwalk').setLevel(loglevel)
logging.getLogger('groundsensor').setLevel(10)
logging.getLogger('aux').setLevel(loglevel)
logging.getLogger('rgbleds').setLevel(loglevel)

# /* Initialize Sub-modules */
#######################################################################

# /* Init web3.py */
mainlogger.info('Initialising Python Geth Console...')
w3 = init_web3()
sc = registerSC(w3)

# /* Init an instance of peer for this Pi-Puck */
robotEN  = w3.geth.admin.nodeInfo().enode
robotKEY = w3.eth.coinbase
me = Peer(robotID, robotEN, robotKEY)
	
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
# "Estimate"  (Rate 1Hz)  queries groundsensor and generates a robot estimate (opinion)
# "Buffer"    (Rate 1Hz) queries RandB to get neighbor identities and add/remove on Geth
# "Event"  (Every block) when a new block is detected make blockchain queries/sends/log block data 

def Estimate(rate = estimateRate):
	""" Control routine to update the local estimate of the robot """
	global estimate
	estimate = 0
	totalWhite = 0
	totalBlack = 0

	while True:

		if time.time()-startTime > timeLimit:
			STOP()
			time.sleep(10)
			os.system('sudo reboot now')

		if not startFlag:
			mainlogger.info('Stopped Estimating')
			break

		tic = TicToc(rate, 'Estimate')

		newValues = gs.getAvg()
		if newValues:	
			totalWhite += sum([x >= gsThresh[i] for i, x in enumerate(newValues)])
			totalBlack += sum([x < gsThresh[i] for i, x  in enumerate(newValues)])
			estimate = (0.5+totalWhite)/(totalWhite+totalBlack+1)

			if isByz:	
				estimate = 0

			estimatelog.log([round(estimate,3),totalWhite,totalBlack,newValues[0],newValues[1],newValues[2]])
		else:
			estimatelog.log([None]) 

		tic.toc()

def Buffer(rate = bufferRate, ageLimit = ageLimit):
	""" Control routine for robot-to-robot dynamic peering """
	global erbTimeout, timeoutStamp
	erbTimeout = 0
	timeoutStamp = 0
	def globalBuffer():
		tcp.unlock()
		with open('pi-pucks.txt', 'r') as peerFile:
			for newId in peerFile:
				newId = newId.strip()
				pb.addPeer(newId)

		for peer in pb.buffer: 
			if int(me.id) > int(peer.id):
				try:
					peer.enode = tcp.request(newPeer.ip, tcp.port)
					w3.geth.admin.addPeer(peer.enode)
					bufferlogger.debug('Peered to %s', peer.id)
				except:
					bufferlogger.debug('Failed to peer to %s', peer.id)


	def localBuffer():
		pb.step()
		gethEnodes = getEnodes()
		gethIds = getIds(gethEnodes)
		global erb, erbTimeout, timeoutStamp

		# Perform buffering tasks for each peer currently in buffer
		for peer in pb.buffer:
			if peer.isDead:
				tcp.unallow(peer.id)
				bufferlogger.debug('Unallowed peer %s @ age %.2f', peer.id, peer.age)

				if peer.id in gethIds:
					if not peer.enode:
						peer.enode = getEnodeById(peer.id, gethEnodes)
					w3.provider.make_request("admin_removePeer",[peer.enode])
					gethIds.remove(peer.id)
					bufferlogger.debug('Removed peer %s @ age %.2f', peer.id, peer.age)

				else:
					pb.removePeer(peer.id)
					bufferlogger.debug('Killed peer %s @ age %.2f', peer.id, peer.age)

				continue

			# elif int(me.id) > int(peer.id) and peer.timeout<=0:
			elif peer.timeout<=0:
				if not peer.enode: 
					try:
						peer.enode = tcp.request(peer.ip, tcp.port)
						bufferlogger.debug('Requested peer enode %s @ age %.2f', peer.id, peer.age)   		 
					except:
						peer.trials += 1
						if peer.trials == 5: 
							peer.setTimeout()
							bufferlogger.warning('Timed-out peer  %s @ age %.2f', peer.id, peer.age)
						continue
				else:
					if peer.id not in gethIds:
						w3.geth.admin.addPeer(peer.enode)
						peer.setTimeout(3)  
						bufferlogger.debug('Added peer %s @ age %.2f', peer.id, peer.age)


		# Turn on LEDs accordingly
		nPeers = len(gethIds)
		if nPeers >= 2:
			rw.setLEDs(0b11111111)
		elif nPeers == 1:
			rw.setLEDs(0b01010101)
		elif nPeers == 0:
			rw.setLEDs(0b00000000)

		# Remove peers which are in geth but not in buffer
		for peerId in getDiff():
			enode = getEnodeById(peerId, gethEnodes)
			w3.provider.make_request("admin_removePeer",[enode])
			tcp.unallow(peerId)
			bufferlogger.warning('Removed ilegittimate peer: %s',peerId)

		# Collect new peer IDs from E-RANDB to the buffer
		# erbIds = erb.getNew()
		erbIds = set()
		# Temporary fix to gctronics bug
		if erbTimeout == 0:
			if not erb.hasFailed():
				erbIds = erb.getNew()
			else:
				bufferlogger.warning('Timing out ERB due to I2C error')
				erb.stop()
				erbTimeout = 2
				timeoutStamp = time.time()
				
		else:
			print('Timed out')
			if (erbTimeout - (time.time() - timeoutStamp)) <= 0:
				erbTimeout = 0
				erb = ERANDB(erbDist, erbtFreq)
				erb.start()


		pb.addPeer(erbIds)
		for erbId in erbIds:
			tcp.allow(erbId)	

		# Logs	
		if bufferlog.isReady():
			# Low frequency logging of chaindata size and cpu usage
			chainSize = getFolderSize('/home/pi/geth-pi-pucks/geth')
			cpuPercent= getCPUPercent()
			extralog.log([chainSize,cpuPercent])
			bufferlog.log([len(gethIds), len(erbIds), len(tcp.allowed), ';'.join(erbIds), ';'.join(gethIds), ';'.join(tcp.allowed)])
		
	while True:
		if not startFlag:
			gethEnodes = getEnodes()
			for enode in gethEnodes:
				w3.provider.make_request("admin_removePeer",[enode])
			mainlogger.info('Stopped Buffering')
			break

		tic = TicToc(rate, 'Buffer')
				
		if globalPeers:
			globalBuffer()
			break
		else:
			localBuffer()

		tic.toc()
	
def Event(rate = eventRate):
	""" Control routine to perform tasks triggered by an event """
	# sc.events.your_event_name.createFilter(fromBlock=block, toBlock=block, argument_filters={"arg1": "value"}, topics=[])
	
	global voteHashes, voteHash
	blockFilter = w3.eth.filter('latest')
	myVoteCounter = 0
	myOkVoteCounter = 0
	voteHashes = []
	voteHash = None
	ticketPrice = 40
	amRegistered = False

	def vote():
		nonlocal myVoteCounter, myOkVoteCounter
		myVoteCounter += 1
		try:
			vote = int(estimate*1e7)
			voteHash = sc.functions.sendVote(vote).transact({'from': me.key,'value': w3.toWei(ticketPrice,'ether'), 'gas':gasLimit, 'gasPrice':gasprice})
			txList.append(voteHash)
			# voteReceipt = w3.eth.waitForTransactionReceipt(voteHash, timeout=120)

			votelog.log([vote])
			myOkVoteCounter += 1
			votelogger.debug('Voted successfully: %.2f (%i/%i)', estimate, myOkVoteCounter, myVoteCounter)
			rgb.flashGreen()

			return voteHash

		except ValueError as e:
			votelog.log(['Value Error'])
			votelogger.debug('Failed to vote: (%i/%i). Error: %s', myOkVoteCounter, myVoteCounter, e)
			rgb.flashRed()

		except Exception as e:
			votelogger.error('Failed to vote: (Unexpected)', e)
			rgb.flashRed()

	def blockHandle():
		""" Tasks when a new block is added to the chain """

		# 1) Log relevant block details 
		block = w3.eth.getBlock(blockHex)
		txPending = str(eval(w3.geth.txpool.status()['pending']))
		txQueue = str(eval(w3.geth.txpool.status()['queued']))

		blocklog.log([time.time()-block.timestamp, round(block.timestamp-blocklog.tStart, 3), block.number, block.hash.hex(), block.parentHash.hex(), block.difficulty, block.totalDifficulty, block.size, len(block.transactions), len(block.uncles), txPending, txQueue])

	def scHandle():
		""" Interact with SC when new blocks are synchronized """
		global ubi, payout, newRound, balance

		# 2) Log relevant smart contract details
		blockNr = w3.eth.blockNumber
		balance = getBalance()
		ubi = sc.functions.askForUBI().call({'gas':gasLimit})
		payout = sc.functions.askForPayout().call({'gas':gasLimit})
		robotCount = sc.functions.getRobotCount().call()
		mean = sc.functions.getMean().call()
		voteCount = sc.functions.getVoteCount().call()
		voteOkCount = sc.functions.getVoteOkCount().call()
		myVoteCounter = sc.functions.robot(me.key).call()[-2]
		myVoteOkCounter = sc.functions.robot(me.key).call()[-1]
		newRound = sc.functions.isNewRound().call()
		consensus = sc.functions.isConverged().call()

		sclog.log([blockNr, balance, ubi, payout, robotCount, mean, voteCount, voteOkCount, myVoteCounter,myVoteOkCounter, newRound, consensus])

		rgb.flashWhite(0.2)

		if consensus == 1:
			rgb.setLED(rgb.all, [rgb.green]*3)
			rgb.freeze()
		elif rgb.frozen:
			rgb.unfreeze()

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

			if not amRegistered:
				amRegistered = sc.functions.robot(me.key).call()[0]
				if amRegistered:
					eventlogger.debug('Registered on-chain')

			if amRegistered:

				try:
					scHandle()
				except Exception as e:
					eventlogger.warning(e)
				else:
					if ubi != 0:
						ubiHash = sc.functions.askForUBI().transact({'gas':gasLimit})
						eventlogger.debug('Asked for UBI: %s', ubi)
						txList.append(ubiHash)

					if payout != 0:
						payHash = sc.functions.askForPayout().transact({'gas':gasLimit})
						eventlogger.debug('Asked for payout: %s', payout)
						txList.append(payHash)

					if newRound:
						try:
							updateHash = sc.functions.updateMean().transact({'gas':gasLimit})
							txList.append(updateHash)
							eventlogger.debug('Updated mean')
						except Exception as e:
							eventlogger.debug(str(e))

					if balance > 40.5 and voteHash == None:
						voteHash = vote()
						voteHashes.append(voteHash)

					if voteHash:
						try:
							tx = w3.eth.getTransaction(voteHash)
							txIndex = tx['transactionIndex']
							txBlock = tx['blockNumber']
							txNonce = tx['nonce']
						except:
							votelogger.warning('Vote disappered wtf. Voting again.')
							voteHash = None

						try:
							txRecpt = w3.eth.getTransactionReceipt(voteHash)
							votelogger.debug('Vote included in block!')
							# print(txRecpt['blockNumber'], txRecpt['transactionIndex'], txRecpt['status'], txBlock, txIndex, txNonce)
							voteHash = None
						except:
							votelogger.debug('Vote not yet included on block')

		tic.toc()

# /* Initialize background daemon threads for the Main-Modules*/
#######################################################################

estimateTh = threading.Thread(target=Estimate, args=())
estimateTh.daemon = True   

bufferTh = threading.Thread(target=Buffer, args=())
bufferTh.daemon = True                         

eventTh = threading.Thread(target=Event, args=())
eventTh.daemon = True                        

# Ignore mainmodules by removing from list:
mainmodules = [estimateTh, bufferTh, eventTh]
# mainmodules = [estimateTh]

def START(modules = submodules + mainmodules, logs = logmodules):
	mainlogger.info('Starting Experiment')
	global startFlag, startTime
	startTime = time.time()

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



def STOP(modules = submodules, logs = logmodules):
	mainlogger.info('Stopping Experiment')
	global startFlag

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
			
	if isByz:
		pass
		mainlogger.info('This Robot was BYZANTINE')

	txlog.start()
	
	for txHash in txList:

		try:
			tx = w3.eth.getTransaction(txHash)
		except:
			txlog.log(['Lost'])
		else:
			try:
				txRecpt = w3.eth.getTransactionReceipt(txHash)
				mined = 'Yes' 
				txlog.log([mined, txRecpt['blockNumber'], tx['nonce'], tx['value'], txRecpt['status'], txHash.hex()])
			except:
				mined = 'No' 
				txlog.log([mined, mined, tx['nonce'], tx['value'], 'No', txHash.hex()])

	txlog.close()

def signal_handler(sig, frame):
	if not startFlag:
		mainlogger.info('Experiment has not started. Exiting')
		sys.exit()
	elif startFlag:
		print('Experiment is running. Type STOP() to stop')


signal.signal(signal.SIGINT, signal_handler)	

# /* Some useful functions */
#######################################################################

def getBalance():
	return round(w3.fromWei(w3.eth.getBalance(me.key), 'ether'), 2)

def getDiffEnodes(gethEnodes = None):
	if gethEnodes:
		return set(gethEnodes)-set(pb.getEnodes())-{me.enode}
	else:
		return set(getEnodes())-set(pb.getEnodes())-{me.enode}

def getDiff(gethIds = None):
	if gethIds:
		return set(gethIds)-set(pb.getIds())-{me.id}
	else:
		return set(getIds())-set(pb.getIds())-{me.enode}

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
			mainlogger.info('Synced Time: %s', TIME)
			break
		except:
			time.sleep(1)

def waitForPC():
	while True:
		try:
			pc.enode = tcp.request(pc.ip, tcpPort)
			pc.key = tcp.request(pc.ip, 40422)
			w3.geth.admin.addPeer(pc.enode)
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
	registerHash = sc.functions.registerRobot().transact({'gas':gasLimit, 'gasPrice':gasprice})
	txList.append(registerHash)

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
		registerHash = sc.functions.registerRobot().transact({'gas':gasLimit, 'gasPrice':gasprice})
		txList.append(registerHash)

		input("Press Enter to start experiment")
		isByz = 1
		START()
		mainlogger.info('Type Ctrl+C to stop experiment')
		mainlogger.info('Robot ID: %s (Byzantine)', me.id)

	elif sys.argv[1] == '--nowalk':

		# /* Wait for Time Synchronization */ 
		mainlogger.info('Waiting for Time Sync...')
		waitForTS()

		# /* Register robot to the Smart Contract*/
		registerHash = sc.functions.registerRobot().transact({'gas':gasLimit, 'gasPrice':gasprice})
		txList.append(registerHash)

		input("Press Enter to start experiment")
		rw.setWalk(False)
		START()
		mainlogger.info('Type Ctrl+C to stop experiment')
		mainlogger.info('Robot ID: %s', me.id)


	# # Alternative start executions
	# elif sys.argv[1] == '--sandbox':
	# 	print('---//--- SANDBOX-MODE ---//---')		
	# 	startFlag = 1	

	# elif sys.argv[1] == '--synctime':
	# 	print('---//--- SYNC-TIME ---//---')
	# 	# /* Wait for Time Synchronization */ 
	# 	waitForTS()
	# 	startFlag = 1

	# elif sys.argv[1] == '--peer2pc':
	# 	print('---//--- PEER-PC ---//---')
	# 	# /* Wait for PC Enode */
	# 	waitForPC()
	# 	startFlag = 1	



# # Correct way to log to file: Setup a new handler and log everything..
# logFormatter = logging.Formatter('[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
# fileHandler = logging.FileHandler(logFile)
# fileHandler.setFormatter(logFormatter)
# fileHandler.setLevel(fileloglevel)
# if fileloglevel != 0:
# 	logging.getLogger('main').addHandler(fileHandler)
# 	logging.getLogger('estimate').addHandler(fileHandler)
# 	logging.getLogger('buffer').addHandler(fileHandler)
# 	logging.getLogger('events').addHandler(fileHandler)
# 	logging.getLogger('voting').addHandler(fileHandler)
# 	logging.getLogger('console').addHandler(fileHandler)
# 	logging.getLogger('erandb').addHandler(fileHandler)
# 	logging.getLogger('randomwalk').addHandler(fileHandler)
# 	logging.getLogger('groundsensor').addHandler(fileHandler)
# 	logging.getLogger('aux').addHandler(fileHandler)
# 	logging.getLogger('rgbleds').addHandler(fileHandler)