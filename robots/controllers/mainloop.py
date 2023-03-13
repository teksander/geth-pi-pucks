#!/usr/bin/env python3
# This is the main control loop running in each robot
# Optional flags:
# --byz       (starts experiment as a byzantine robot)
# --sandbox   (control sensors and actuators without starting experiment)
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
rwSpeed = 600
pcID = '100'

estimateRate = 1
voteRate = 45
bufferRate = 0.33
eventRate = 1
globalPeers = 0
ageLimit = 2

timeLimit = 1800

DECIMAL_FACTOR =  1e6
DEPOSITFACTOR = 4 #portion of assets deposted to support each vote
# /* Global Variables */
#######################################################################
global startFlag, isByz
startFlag = False
isByz = False

global gasLimit, gasprice, gas
gasLimit = 0x9000000
gasprice = 0x000000 #no gas fee in our configuration
gas = 0x00000

global txList, startTime
txList = []


# /* Import Packages */
#######################################################################
import logging
if logtofile:
	logFile = '../logs/loggers.txt'
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
from groundsensor import GroundSensor
from colorguidedwalk import ColorWalkEngine
from rgbleds import RGBLEDs
from statemachine import *
from aux import *


global clocks
clocks = dict()
clocks['query_sc'] = Timer(1)
# Global parameters
# subprocess.call("source ../../globalconfig")

# Calibrated parameters
#with open('../calibration/gsThreshes.txt') as calibFile:
#	gsThresh = list(map(int, calibFile.readline().split()))

# /* Initialize Logging Files and Console Logging*/
#######################################################################

# Experiment data logs (recorded to file)
header = ['ESTIMATE','W','B','S1','S2','S3']
estimatelog = Logger('../logs/estimate.csv', header, 10)

header = ['#BUFFER', '#GETH','#ALLOWED', 'BUFFERPEERS', 'GETHPEERS','ALLOWED']
bufferlog = Logger('../logs/buffer.csv', header, 2)

header = ['VOTE']
votelog = Logger('../logs/vote.csv', header)

header = ['TELAPSED','TIMESTAMP','BLOCK', 'HASH', 'PHASH', 'DIFF', 'TDIFF', 'SIZE','TXS', 'UNC', 'PENDING', 'QUEUED']
blocklog = Logger('../logs/block.csv', header)

header = ['BLOCK', 'BALANCE', 'UBI', 'PAY','#ROBOT', 'MEAN', '#VOTES','#OKVOTES', '#MYVOTES','#MYOKVOTES', 'R?','C?']
sclog = Logger('../logs/sc.csv', header)

header = ['#BLOCKS']
synclog = Logger('../logs/sync.csv', header)

header = ['CHAINDATASIZE', '%CPU']
extralog = Logger('../logs/extra.csv', header, 5)

header = ['MINED?', 'BLOCK', 'NONCE', 'VALUE', 'STATUS', 'HASH']
txlog = Logger('../logs/tx.csv', header)

# List of logmodules --> iterate .start() to start all; remove from list to ignore
logmodules = [estimatelog, bufferlog, votelog, blocklog, sclog, synclog, extralog, txlog]

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

robotID = open("/boot/pi-puck_id", "r").read().strip()

# /* Init web3.py */
mainlogger.info('Initialising Python Geth Console...')
w3 = init_web3()
sc = registerSC(w3)

# /* Init an instance of peer for this Pi-Puck */
me = Peer(robotID, w3.enode, w3.key)

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
#cwe inits a gs instance as well
#gs = GroundSensor(gsFreq)

# /* Init Random-Walk, __walking process */
mainlogger.info('Initialising walking controller...')
#color walk engine without .start()
cwe = ColorWalkEngine(rwSpeed)
#cwe=None
global color_idx, verified_colors, verified_idx
color_idx = cwe.get_color_list()
verified_colors=[0 for x in range(len(color_idx))]
verified_idx=[]

# /* Init LEDs */
rgb = RGBLEDs()

# List of submodules --> iterate .start() to start all
submodules = [w3.geth.miner, tcp, erb]
global fsm
fsm = FiniteStateMachine(start=Idle.IDLE)

global color_to_verify, color_to_report
color_to_verify = [0, 0, 0]
color_to_report = [0, 0, 0]

# /* Define Main-modules */
#######################################################################
# The 4 Main-modules: 
# "Buffer"    (Rate 1Hz) queries RandB to get neighbor identities and add/remove on Geth
# "Event"  (Every block) when a new block is detected make blockchain queries/sends/log block data 

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
			cwe.set_leds(0b11111111)
		elif nPeers == 1:
			cwe.set_leds(0b01010101)
		elif nPeers == 0:
			cwe.set_leds(0b00000000)

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
			chainSize = getFolderSize('/home/pi/geth-pi-pucks/blockchain/geth')
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

def Main(rate = eventRate):
	global fsm, voteHashes, voteHash, color_to_verify, color_to_report
	blockFilter = w3.eth.filter('latest')
	voteHashes = []
	voteHash = None
	while True:
		if not startFlag:
			mainlogger.info('Stopped Events')
			break
		tic = TicToc(rate, 'Event')
		newBlocks = blockFilter.get_new_entries()
		if fsm.query(Idle.IDLE):
			fsm.setState(Scout.Query, message="Start exploration")
		elif fsm.query(Scout.Query):
			# check reported color.
			verify_unseen = 0
			#check if any cluster avaiting verification on chain
			if clocks['query_sc'].query():
				source_list = sc.functions.getSourceList().call()
				points_list = sc.functions.getPointListInfo().call()
				print("get source list: ", source_list)
				if len(source_list) > 0:
					candidate_cluster = []
					for idx, cluster in enumerate(source_list):
						verified_by_me = False
						for point_rec in points_list:
							if point_rec[5] == me.key and int(point_rec[4]) == idx:
								verified_by_me = True
						if cluster[3] == 0 and not verified_by_me:  # exists cluster needs verification
							candidate_cluster.append((cluster, idx))
					if len(candidate_cluster) > 0:
						# randomly select a cluster to verify
						# no longer needed to maintain the verified index list, as we used the verified_by_me check above
						# idx_to_verity = random.randrange(len(candidate_cluster))
						select_idx = candidate_cluster[random.randrange(len(candidate_cluster))]
						cluster = candidate_cluster[select_idx][0]
						fsm.setState(Verify.DriveTo, message="Go to unverified source")
						color_to_verify[0] = float(cluster[0]) / DECIMAL_FACTOR
						color_to_verify[1] = float(cluster[1]) / DECIMAL_FACTOR
						color_to_verify[2] = float(cluster[2]) / DECIMAL_FACTOR
						verify_unseen = 1
			if verify_unseen == 0:
				print("try dissover color: ")
				found_color_idx, _, found_color_bgr = cwe.discover_color(10)
				print(found_color_bgr)
				if found_color_bgr != -1:
					for idx in range(3):
						color_to_report[idx] =  found_color_bgr[idx]
					if found_color_idx > -1:
						fsm.setState(Scout.PrepReport, message="Prepare proposal")
				else:
					print('no color found, pass')
		elif fsm.query(Scout.PrepReport):
			vote_support = getBalance()/DEPOSITFACTOR
			tag_id = cwe.check_apriltag() #id = 0 no tag,
			if voteHash !=0 and tag_id !=0:
				print("vote: ",color_to_report,"support: ", vote_support, "tagid: ", tag_id)
				voteHash = sc.functions.reportNewPt([int(color_to_report[0] * DECIMAL_FACTOR),
														int(color_to_report[1] * DECIMAL_FACTOR),
														int(color_to_report[2] * DECIMAL_FACTOR)],
														int(tag_id),
														w3.toWei(vote_support, 'ether'),
														int(tag_id), 0).transact(
					{'from': me.key, 'value': w3.toWei(vote_support, 'ether'), 'gas': gasLimit,
					 'gasPrice': gasprice})

			else:
				#send an empty trasnaction with intention ==3, help updating the SC
				voteHash = sc.functions.reportNewPt([int(0),
													int(0),
													int(0)],
													int(0),
													w3.toWei(0.01, 'ether'),
													0, #this is realType, for debugging
													int(3)).transact(
					{'from': me.key, 'value': w3.toWei(0.01, 'ether'), 'gas': gasLimit,
					 'gasPrice': gasprice})
			fsm.setState(Scout.Query, message="Exit from reporting stage, discover again")
		elif fsm.query(Verify.DriveTo):
			arrived = cwe.drive_to_rgb(color_to_verify, duration=60)
			if arrived:
				tag_id = cwe.check_apriltag()
				_,_,found_color_bgr = cwe.check_all_color() #averaged color of the biggest contour

				vote_support = getBalance() / DEPOSITFACTOR
				if vote_support > 0 and found_color_bgr!=-1:
					for idx in range(3):
						color_to_report[idx] = found_color_bgr[idx]
					print("report bgr color: ", color_to_report)
					voteHash = sc.functions.reportNewPt([int(color_to_report[0] * DECIMAL_FACTOR),
															   int(color_to_report[1] * DECIMAL_FACTOR),
															   int(color_to_report[2] * DECIMAL_FACTOR)],
															   int(tag_id),
															   w3.toWei(vote_support, 'ether'),
															int(tag_id), 0).transact(
						{'from': me.key, 'value': w3.toWei(vote_support, 'ether'), 'gas': gasLimit,
						 'gasPrice': gasprice})
				else:
					# send an empty trasnaction with intention ==3, help updating the SC
					voteHash = sc.functions.reportNewPt([int(0),
														int(0),
														int(0)],
														int(0),
														w3.toWei(0.01, 'ether'),
														0, int(3)).transact(
						{'from': me.key, 'value': w3.toWei(0.01, 'ether'), 'gas': gasLimit,
						 'gasPrice': gasprice})
			fsm.setState(Scout.Query, message="Resume scout")

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
bufferTh = threading.Thread(target=Buffer, args=())
bufferTh.daemon = True

eventTh = threading.Thread(target=Main, args=())
eventTh.daemon = True

# Ignore mainmodules by removing from list:
mainmodules = [bufferTh, eventTh]
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
	#Main(eventRate)



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
		STOP()
		print('Experiment is stopped. Exiting')
		sys.exit()
		

signal.signal(signal.SIGINT, signal_handler)

# /* Some useful functions */
#######################################################################

def getBalance():
	#check all my balance, including those frozen in unverified clusters.
	myBalance = float(w3.fromWei(w3.eth.getBalance(me.key),"ether"))
	points_list = sc.functions.getPointListInfo().call()
	source_list = sc.functions.getSourceList().call()
	for idx, cluster in enumerate(source_list):
		if cluster[3] == 0:
			for point_rec in points_list:
				if point_rec[5] == me.key and int(point_rec[4]) == idx:
					myBalance += float(point_rec[2]) / 1e18
	return round(myBalance, 2)

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

# /* BEGIN EXPERIMENT */
#######################################################################

input("Press Enter to start experiment")

if len(sys.argv) == 1:
	
	START()
	mainlogger.info('Robot ID: %s', me.id)

elif len(sys.argv) == 2:
	if sys.argv[1] == '--byz':
		isByz = 1

		START()
		mainlogger.info('Robot ID: %s (Byzantine)', me.id)

	elif sys.argv[1] == '--nowalk':
		cwe.rot.setWalk(False)

		START()
		mainlogger.info('Robot ID: %s', me.id)

	elif sys.argv[1] == '--sandbox':
		print('---//--- SANDBOX-MODE ---//---')
		startFlag = 1

mainlogger.info('Type Ctrl+C to stop experiment')
