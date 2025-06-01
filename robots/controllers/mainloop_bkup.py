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
erbDist = 50
erbtFreq = 10
gsFreq = 20
rwSpeed = 600
pcID = '100'

estimateRate = 1
voteRate = 45
bufferRate = 0.33
mainRate = 1
eventRate = 1
globalPeers = 0
ageLimit = 2

timeLimit = 1800

# /* Global Variables */
#######################################################################

global startFlag, startTime
startFlag, startTime = False, 0

global gasLimit, gasprice, gas
gasLimit, gasprice, gas  = 0x9000000, 0x000000, 0x00000

global txList, clocks
txList, clocks = [], dict()

global color_to_report, color_to_verify, color_name_to_report, color_name_to_verify
global color_idx_to_report, cluster_idx_to_verify, recent_colors
color_to_verify = [0, 0, 0]
color_to_report = [0, 0, 0]
color_name_to_verify = ''
color_name_to_report = ''
color_idx_to_report   = 0
cluster_idx_to_verify = 0
recent_colors=[]

global voteHash, balance_global, lastblock_global, allpoints_global, allclusters_global
voteHash = None
balance_global   = 0
lastblock_global = 0	
allpoints_global, allclusters_global = dict(), dict()

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
import sys
import copy
from console import init_web3, registerSC
from erandb import ERANDB
from groundsensor import GroundSensor
from colorguidedwalk import ColorWalkEngine
from rgbleds import RGBLEDs
from statemachine import *
from aux import *

# Global parameters
# subprocess.call("source ../../globalconfig")
# print(os.environ['DECIMAL_FACTOR'])
# print(os.environ['MAXUNVCLUSTER'])
DECIMAL_FACTOR =  1e5
DEPOSITFACTOR = 3

global isByz, isFau, isCol, behaviour
isByz = True if len(sys.argv)>1 and sys.argv[1] == '--byz' else False
isFau = True if len(sys.argv)>1 and sys.argv[1] == '--fau' else False
isCol = True if len(sys.argv)>1 and sys.argv[1] == '--col' else False

behaviour = 'malicious' if isByz else 'faulty' if isFau else 'colluding' if isCol else 'honest'

# Calibrated parameters
#with open('../calibration/gsThreshes.txt') as calibFile:
#	gsThresh = list(map(int, calibFile.readline().split()))

# /* Initialize Console Logging*/
#######################################################################

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
logging.getLogger('aux').setLevel(loglevel)
logging.getLogger('rgbleds').setLevel(loglevel)
logging.getLogger('cwe').setLevel(10 if isFau else 50)

# /* Initialize Logging Files */
#######################################################################

# Experiment data logs (recorded to file)

# header = ['#BUFFER', '#GETH','#ALLOWED', 'BUFFERPEERS', 'GETHPEERS','ALLOWED']
# bufferlog = Logger('../logs/buffer.csv', header, 2)

header = ['TELAPSED','TIMESTAMP','BLOCK', 'HASH', 'PHASH', 'DIFF', 'TDIFF', 'SIZE','TXS', 'UNC', 'PENDING', 'QUEUED']
blocklog = Logger('../logs/block.csv', header)

header = ['BLOCK','HASH', 'BALANCE', 'SPENDABLE', 'SCBAL', 'PENDING', '#CLUSTERS', '#ACCEPT', '#REJECT', '#PENDING', 'RS1', 'RS2', 'RS3', 'RS4']
sclog = Logger('../logs/sc.csv', header, extrafields={'isbyz':isByz, 'isfau':isFau, 'iscol': isCol, 'type':behaviour})

header = ['B','G','R', 'NAME', 'IDX', 'FOOD', 'SUPPORT','STATE']
colorlog = Logger('../logs/color.csv', header, extrafields={'isbyz':isByz, 'isfau':isFau, 'iscol': isCol, 'type':behaviour})

header = ['MEM', '%CPU', '%RAM']
extralog = Logger('../logs/extra.csv', header, 10)

# List of logmodules --> iterate .start() to start all; remove from list to ignore
logmodules = [blocklog, sclog, colorlog, extralog]

# /* Initialize Sub-modules */
#######################################################################

robotID = open("/boot/pi-puck_id", "r").read().strip()

# /* Init web3.py and the smart contract */
mainlogger.info('Initialising Python Geth Console...')
w3 = init_web3()
sc = registerSC(w3)

# /* Init an instance of peer for this Pi-Puck */
me = Peer(robotID, w3.enode, w3.key)

# /* Init an instance of peer for the monitor PC */
pc = Peer(pcID)

# /* Init an instance of the buffer for peers  */
pb = PeerBuffer(ageLimit)

# /* Init TCP server, __hosting process and request function */
mainlogger.info('Initialising TCP server...')
tcp = TCP_server(me.enode, me.ip, tcpPort)

# /* Init E-RANDB __listening process and transmit function
mainlogger.info('Initialising RandB board...')
erb = ERANDB(erbDist, erbtFreq)

# /* Init Color-Guided walk, __walking process */
mainlogger.info('Initialising color tracking controller...')
cwe = ColorWalkEngine(rwSpeed, [1,1,0.75] if isFau else [1,1,1])

# /* Init LEDs */
rgb = RGBLEDs()

# /* Init FSM */
fsm = FiniteStateMachine(start=Idle.Start)

# List of submodules --> iterate .start() to start all
submodules = [w3.geth.miner, tcp, erb]

color_names = cwe.get_color_list()
print("Calibrated colors:", color_names)

# balance_global = float(w3.fromWei(w3.eth.getBalance(me.key), "ether"))
# /* Define Main-modules */
#######################################################################

# The 4 Main-modules: 
# "Buffer"    (Rate 1Hz) queries RandB to get neighbor identities and add/remove on Geth
# "Main""     (Rate 1Hz) performs the main control loop
# "Event"     (Rate 1Hz) when a new block is detected make blockchain queries for logging

def Buffer(rate = bufferRate):
	""" Control routine for robot-to-robot dynamic peering """
	global erbTimeout, timeoutStamp
	erbTimeout = 0
	timeoutStamp = 0
	
	def globalBuffer():
		pass
		# tcp.unlock()
		# with open('pi-pucks.txt', 'r') as peerFile:
		# 	for newId in peerFile:
		# 		newId = newId.strip()
		# 		pb.addPeer(newId)

		# for peer in pb.buffer:
		# 	if int(me.id) > int(peer.id):
		# 		try:
		# 			peer.enode = tcp.request(newPeer.ip, tcp.port)
		# 			w3.geth.admin.addPeer(peer.enode)
		# 			bufferlogger.debug('Peered to %s', peer.id)
		# 		except:
		# 			bufferlogger.debug('Failed to peer to %s', peer.id)


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
					try:
						if not peer.enode:
							peer.enode = getEnodeById(peer.id, gethEnodes)
						w3.provider.make_request("admin_removePeer",[peer.enode])
						gethIds.remove(peer.id)
						bufferlogger.debug('Removed peer %s @ age %.2f', peer.id, peer.age)
					except:
						bufferlogger.debug('Error removing peer %s', peer.id)
						print('Error removing peer')
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

		# Remove peers which are in geth but not in buffer
		for peerId in getDiff():
			try:
				enode = getEnodeById(peerId, gethEnodes)
				w3.provider.make_request("admin_removePeer",[enode])
				tcp.unallow(peerId)
				bufferlogger.warning('Removed ilegittimate peer: %s',peerId)
			except:
				print('Error removing ilegittimate peer')

		# Collect new peer IDs from E-RANDB to the buffer
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

		# # Turn on LEDs accordingly
		# nPeers = len(gethIds)
		# if nPeers >= 2:
		# 	cwe.set_leds(0b11111111)
		# elif nPeers == 1:
		# 	cwe.set_leds(0b01010101)
		# elif nPeers == 0:
		# 	cwe.set_leds(0b00000000)

		# if bufferlog.query():
		# 	bufferlog.log([len(gethIds), len(erbIds), len(tcp.allowed), ';'.join(erbIds), ';'.join(gethIds), ';'.join(tcp.allowed)])
	
	tic = TicToc(rate, 'Buffer')

	while startFlag:
		tic.tic()

		if globalPeers:
			globalBuffer()
			break
		else:
			localBuffer()

		tic.toc()

	mainlogger.info('Stopped Buffering')

	gethEnodes = getEnodes()
	for enode in gethEnodes:
		w3.provider.make_request("admin_removePeer",[enode])

def Main(rate = mainRate):
	""" Main control routine """
	global fsm, voteHash, color_to_verify, color_to_report, color_name_to_report, color_name_to_verify, recent_colors, cluster_idx_to_verify, color_idx_to_report

	tic = TicToc(rate, 'Main')
		 
	while startFlag:
		tic.tic()

		if fsm.query(Idle.Start):
			fsm.setState(Scout.Query, message="Start exploration")

		elif fsm.query(Scout.Query):

			# check reported color.
			# rgb.setAll(rgb.off)
			explore = True
			verify  = True
			
			# query the Smart Contract 
			all_clusters = copy.copy(allclusters_global)
			all_points   = copy.copy(allpoints_global)
			vote_support, current_balance = getBalance_global()

			# # this is for a test: idle and wait if no assets
			# vote_support /= DEPOSITFACTOR
			# if vote_support >= current_balance and current_balance!=0:
			# 	rgb.setAll('white')
			# 	verify  = False
			# 	explore = False
			# 	time.sleep(1)

			# check if any cluster avaiting verification on chain
			if verify and len(all_clusters) > 0:
				candidate_cluster  = []
				unverified_clusters = 0
				for idx, cluster in enumerate(all_clusters):
					
					verified_by_me = False
					for point_rec in all_points:
						if point_rec['sender'] == me.key and point_rec['cluster'] == idx:
							verified_by_me = True

					if cluster['verified'] == 0:
						unverified_clusters += 1

						if not verified_by_me and any([int(a) for a in cluster['position']]):
							candidate_cluster.append((cluster, idx))

				# # this is for a test: idle and wait if no clusters to verify
				if unverified_clusters == DEPOSITFACTOR and len(candidate_cluster) == 0:
					print("no candidates to verify and max cluster count reached")
					rgb.setAll('white')
					verify  = False
					explore = False
					time.sleep(1)
					
				# randomly select a cluster to verify
				if verify and len(candidate_cluster) > 0:
					print("my candidates to verify: ", [cluster[1] for cluster in candidate_cluster])
					select_idx = random.randrange(len(candidate_cluster))
					cluster = candidate_cluster[select_idx][0]
					cluster_idx_to_verify = candidate_cluster[select_idx][1]+1 # make sure this +1 is correct
					color_to_verify = [float(a)/DECIMAL_FACTOR for a in cluster['position']]
			
					fsm.setState(Verify.DriveTo, message=f"Verify cluster idx {cluster_idx_to_verify}")
					explore = False

			if explore:
				
				print("try to discover color: ")
				found_color_idx, found_color_name, found_color_bgr = cwe.discover_color(10)

				if found_color_bgr != -1:
					print(f"Found color: {found_color_name} {[int(a) for a in found_color_bgr]}")
					# rgb.setAll(found_color_name)
					for idx in range(3):
						color_to_report[idx] = found_color_bgr[idx]
					color_name_to_report = found_color_name
					color_idx_to_report = found_color_idx

					if found_color_idx > -1 and color_name_to_report not in recent_colors:
						fsm.setState(Scout.PrepReport, message="Found color by exploring")

					elif color_name_to_report in recent_colors:
						print("found recently seen color, pass")
						cwe.random_walk_engine(10, 10)

				else:
					print('no color found, pass')

		elif fsm.query(Scout.PrepReport):
			
			print(f"Drive to report: {color_name_to_report}, {[int(a) for a in color_to_report]}") 
			# rgb.setAll(color_name_to_report)
			
			arrived, _ , _ = cwe.drive_to_closest_color(color_to_report, duration=100) 

			if arrived:
				vote_support, address_balance = getBalance_global()
				vote_support /= DEPOSITFACTOR
				tag_id, _ = cwe.check_apriltag()

				print("find tag id: ", tag_id, vote_support, address_balance)
				if tag_id != 0 and vote_support < address_balance:

					# two recently discovered colord are recorded in recent_colors
					recent_colors.append(color_name_to_report)
					recent_colors = recent_colors[-2:]

					# repeat sampling of the color to report
					print("found color, start repeat sampling...")
					repeat_sampled_color = cwe.repeat_sampling(color_name=color_name_to_report, repeat_times=3)
					if repeat_sampled_color[0] !=-1:
						color_to_report = repeat_sampled_color
					else:
						print("color repeat sampling failed, report one time measure")

					
					is_useful = int(tag_id) == 2
					if isByz:
						is_useful = not is_useful
					if isCol:
						is_useful = color_name_to_report == 'blue' 

					colorlog.log(list(color_to_report)+[color_name_to_report, color_idx_to_report, is_useful, vote_support,'scout'])

					voteHash = sendVote(color_to_report, is_useful, vote_support, color_idx_to_report, 0)
					print_color("Report vote: ", voteHash.hex()[0:8],
								"color: ", [int(a) for a in color_to_report], color_name_to_report, 
								"support: ", vote_support,
								"tagid: ", tag_id, 
								"vote: ", is_useful, 
								color_rgb=[int(a) for a in color_to_report])		

					fsm.setState(Idle.RandomWalk, message="Wait for vote")
			else:
				fsm.setState(Scout.Query, message="Did not arrive")

		elif fsm.query(Verify.DriveTo):

			# Temporary check due to bug where robot goes to verify [0,0,0]:
			if not any([int(a) for a in color_to_verify]):
				print('GOING TO VERIFY ORIGIN!! Bug not fixed')
				color_to_verify = [int(a * 100000) for a in color_to_verify]
				print(color_to_verify)

			color_name_to_verify, _ = cwe.get_closest_color(color_to_verify)
			print(f"Drive to verify: {color_name_to_verify}, {[int(a) for a in color_to_verify]}") 
			# rgb.setAll(color_name_to_verify)

			# Try to find and drive to the closest color according to the agent's understanding for 100 sec
			arrived, color_name_to_verify, color_idx_to_verify = cwe.drive_to_closest_color(color_to_verify, duration=100)

			if arrived:

				attempts = 0
				while True:

					tag_id,_ = cwe.check_apriltag()
					found_color_idx, found_color_name, found_color_bgr,_ = cwe.check_all_color() #averaged color of the biggest contour
					vote_support, address_balance = getBalance_global()
					vote_support /= DEPOSITFACTOR
					if vote_support >= address_balance:
						attempts += 10
						print(f"Verify fail {attempts}/10: poor {address_balance}<{vote_support}")

					elif found_color_idx != color_idx_to_verify:
						attempts += 1
						print(f"Verify fail {attempts}/10: found {found_color_name}!={color_name_to_verify}")

					elif tag_id == 0:
						attempts += 1
						print(f"Verify fail {attempts}/10: no tag found")
				
					else:
						ok_to_vote = True
						break

					if attempts >= 10:
						fsm.setState(Scout.Query, message="Verification failed")
						ok_to_vote = False
						break
					
					cwe.rot.setPattern_duration(["ccw", "cw"][attempts % 2], attempts//2)

				if ok_to_vote:
					
					is_useful = int(tag_id) == 2
					if isByz:
						is_useful = not is_useful
					if isCol:
						is_useful = color_name_to_verify == 'blue'

					print(f"found color {found_color_name}, start repeat sampling...")
					repeat_sampled_color = cwe.repeat_sampling(color_name=found_color_name, repeat_times=3)
					if repeat_sampled_color[0]!=-1:
						for idx in range(3):
							color_to_report[idx] = repeat_sampled_color[idx]
						colorlog.log(list(color_to_report)+[found_color_name, color_idx_to_verify, is_useful, vote_support, 'verify_rs'])
					else:
						print("repeat sampling failed, report one-time measure")
						for idx in range(3):
							color_to_report[idx] = found_color_bgr[idx]
						colorlog.log(list(color_to_report)+[found_color_name, color_idx_to_verify, is_useful, vote_support, 'verify_f'])
					print("verified and report bgr color: ", color_to_report)

					# colorlog.log(list(color_to_report)+[color_name_to_report, color_idx_to_report, 'verify'])
					voteHash = sendVote(color_to_report, is_useful, vote_support, color_idx_to_verify, cluster_idx_to_verify)
					print_color("Verify vote: ", voteHash.hex()[0:8],
								"color: ", [int(a) for a in color_to_report], found_color_name, 
								"support: ", vote_support, 
								"tagid: ", tag_id, 
								"vote: ", is_useful, 
								color_rgb=[int(a) for a in color_to_report])

					fsm.setState(Idle.RandomWalk, message="Wait for vote")


		elif fsm.query(Idle.RandomWalk):
			if fsm.getCurrentTimer() <=2:
				cwe.rot.setDrivingMode("pattern")
				cwe.rot.setPattern("cw", (random.uniform(0, 1) * 3)+4)
			else:
				cwe.random_walk_engine(15, 3)

			if not voteHash or fsm.getCurrentTimer()>40 or not startFlag:
				voteHash = None
				cwe.set_leds(0b00000000)
				fsm.setState(Scout.Query, message=f"rw duration:{fsm.getCurrentTimer():.2f}")

		elif fsm.query(Idle.ToOtherColor):

			if fsm.getPreviousState() == Scout.PrepReport:
				exclude_color = color_name_to_report
			else:
				exclude_color = color_name_to_verify


			navigation_targets = [this_color for this_color in cwe.colors if this_color != exclude_color]
			navigation_target = random.choice(navigation_targets)
			print("Drive out of the report color, towards: ", navigation_target)
			arrived = cwe.drive_to_color(navigation_target, duration=30, arrival_threshold=40, turn_lambda=1, turn_time=15) #drive to a color different from the latest report
			if arrived:
				cwe.random_walk_engine(10,10)
			if not voteHash or fsm.getCurrentTimer()>40:
				voteHash = None
				cwe.set_leds(0b00000000)
				fsm.setState(Scout.Query, message=f"rw duration:{fsm.getCurrentTimer():.2f}")

		tic.toc()

	mainlogger.info('Stopped Main module')

def Event(rate = eventRate):
	""" Control routine executed each time new blocks are synchronized """
	global voteHash, balance_global, lastblock_global, allpoints_global, allclusters_global

	tic = TicToc(rate, 'Event')

	def blockHandle():
		""" Execute for each block when new blocks are synchronized """

		# Log relevant block details 
		block = w3.eth.getBlock(blockHex)
		blocklog.log([
			time.time()-block.timestamp, 
			round(block.timestamp-blocklog.tStart, 3), 
			block.number, 
			block.hash.hex(), 
			block.parentHash.hex(), 
			block.difficulty, 
			block.totalDifficulty, 
			block.size, 
			len(block.transactions), 
			len(block.uncles), 
			str(eval(w3.geth.txpool.status()['pending'])), 
			str(eval(w3.geth.txpool.status()['queued']))
			])

	def scHandle():
		""" Execute when new blocks are synchronized """

		# Log relevant smart contract details
		blockNumb = lastblock_global['number']
		blockHash = lastblock_global['hash'].hex()
		balance, spendable_balance = getBalance_global()
		rep_stats  = sc.functions.getReportStatistics().call()
		n_clusters = len(allclusters_global)
		n_accepted = len([c for c in allclusters_global if c['verified']==1])
		n_rejected = len([c for c in allclusters_global if c['verified']==2])
		n_pending  = len([c for c in allclusters_global if c['verified']==0])
		scbalance  = sc.functions.balances(w3.eth.coinbase).call()

		sclog.log([blockNumb, 
			 blockHash,
			   balance, 
			   spendable_balance, 
			   float(scbalance/1e18),
			   balance_pending, 
			   n_clusters, 
			   n_accepted, 
			   n_rejected, 
			   n_pending, 	   
			   *rep_stats])

	blockFilter = w3.eth.filter('latest')
	
	while startFlag:
		tic.tic()
		
		newBlocks = blockFilter.get_new_entries()

		if newBlocks:

			balance_global = float(w3.fromWei(w3.eth.getBalance(me.key),"ether"))
			lastblock_global = w3.eth.getBlock('latest')
			_, allpoints_global = getPoints()
			_, allclusters_global = getClusters()

			balance_pending = 0
			# myPendingTxs = 
			# for tx in myPendingTxs:
			# 	balance_pending += tx['value']

			scHandle()

			for blockHex in newBlocks:
				blockHandle()

			if voteHash:
				cwe.set_leds(0b11111111)
				try:
					w3.eth.getTransaction(voteHash)
				except Exception as e:
					print(f'ERROR tx: ', voteHash.hex()[0:8], ' disappered ', {str(e)})
					voteHash = None
					cwe.set_leds(0b00000000)
				try:
					txRecpt = w3.eth.getTransactionReceipt(voteHash)
					print('SUCCESS tx: ', voteHash.hex()[0:8],' included in block: ', txRecpt['blockNumber'])
					if txRecpt['status'] == 0:
						print('ERROR  tx: ', voteHash.hex()[0:8],' status is: ', txRecpt['status'])

					voteHash = None
					cwe.set_leds(0b00000000)

				except Exception as e:
					pass
					# print(f'ERROR tx: ', voteHash.hex()[0:8], ' no receipt ', {str(e)})

		# Low frequency logging of chaindata size and cpu usage
		if extralog.query():
			mem = get_folder_size('/home/pi/geth-pi-pucks/blockchain/geth')
			cpu, ram = get_process_stats('geth ')
			extralog.log([mem, cpu, ram])

		tic.toc()

	mainlogger.info('Stopped Event Module')

# /* Initialize background threads for the Main-Modules*/
#######################################################################
bufferTh = threading.Thread(target=Buffer, args=())
bufferTh.daemon = True

mainTh = threading.Thread(target=Main, args=())
mainTh.daemon = True

eventTh = threading.Thread(target=Event, args=())
eventTh.daemon = True

# Ignore mainmodules by removing from list:
mainmodules = [bufferTh, mainTh, eventTh]

def START(modules = submodules + mainmodules, logs = logmodules):
	global startFlag, startTime

	mainlogger.info('Starting Experiment')

	startTime = time.time()
	for log in logs:
		try:
			log.start()
		except:
			mainlogger.critical('Error Starting Log')

	startFlag = True
	for module in modules:
		try:
			module.start()
		except:
			mainlogger.critical('Error Starting Module')


def STOP(modules = submodules, logs = logmodules):
	global startFlag
	cwe.duration=0
	mainlogger.info('--/-- Stopping Main-modules --/--')
	startFlag = False
	for module in mainmodules:
		module.join()

	mainlogger.info('--/-- Stopping Sub-modules --/--')
	for module in submodules+[cwe]:
		try:
			module.stop()
		except:
			mainlogger.warning('Error stopping submodule')

	for log in logs:
		try:
			log.close()
		except:
			mainlogger.warning('Error Closing Logfile')

	header = cluster_keys
	clusterlog = Logger('../logs/cluster.csv', header)

	clusterlog.start()
	for cluster in sc.functions.getClusters().call():
		cluster = [str(i).replace(', ', ',') for i in cluster]
		clusterlog.log(cluster)
	clusterlog.close()

	header = ['HASH','MINED?', 'STATUS', 'BLOCK', 'NONCE', 'VALUE', ]
	txlog = Logger('../logs/tx.csv', header, extrafields={'isbyz':isByz, 'isfau':isFau, 'iscol': isCol, 'type':behaviour})

	txlog.start()
	for txHash in txList:
		try:
			tx = w3.eth.getTransaction(txHash)
		except:
			txlog.log(['Lost'])
		else:
			try:
				txRecpt = w3.eth.getTransactionReceipt(txHash)
				txlog.log([txHash.hex(), 'Yes', txRecpt['status'], txRecpt['blockNumber'], tx['nonce'], tx['value']])
			except:
				txlog.log([txHash.hex(), 'No', 'No', 'No', tx['nonce'], tx['value']])
	txlog.close()

def signal_handler(sig, frame):

	if startFlag:
		print('--/-- Stopping Experiment --/--')
		STOP()
		print('Experiment is stopped. Exiting')
		sys.exit()
	else:
		mainlogger.info('Experiment never started. Exiting')
		sys.exit()
		

signal.signal(signal.SIGINT, signal_handler)

# /* Some useful functions */
#######################################################################

def sendVote(color_to_report, is_useful, support, color_idx, cluster_idx):
	global txList
	value = w3.toWei(support, 'ether')

	voteHash = sc.functions.reportNewPt(
		[int(a*DECIMAL_FACTOR) for a in color_to_report],
		int(is_useful),
		int(value),
		color_idx,  
		int(cluster_idx)
		).transact({'from': me.key, 'value':value, 'gas': gasLimit, 'gasPrice': gasprice})
	
	txList.append(voteHash)

	return voteHash

cluster_keys = sc.functions.getClusterKeys().call()
def getClusters():
	cluster_list = sc.functions.getClusters().call()
	cluster_dict = [list2dict(c, cluster_keys) for c in cluster_list]
	return cluster_list, cluster_dict

point_keys = sc.functions.getPointKeys().call()
def getPoints():
	point_list = sc.functions.getPoints().call()
	point_dict = [list2dict(c, point_keys) for c in point_list]
	return point_list, point_dict

def getBalance():
	#check all my balance, including those frozen in unverified clusters.
	myUsableBalance = float(w3.fromWei(w3.eth.getBalance(me.key),"ether")) -1
	myBalance = myUsableBalance
	_, allpoints = getPoints()
	_, allclusters = getClusters()
	for idx, cluster in enumerate(allclusters):
		if cluster['verified'] == 0:
			for point in allpoints:
				if point['sender'] == me.key and int(point['cluster']) == idx:
					myBalance += float(point['credit']) / 1e18
	return round(myBalance, 2), myUsableBalance

# def getBalance_global():
# 	#check all my balance, including those frozen in unverified clusters.
# 	chain_balance = balance_global
# 	full_balance = chain_balance
# 	for idx, cluster in enumerate(allclusters_global):
# 		if cluster['verified'] == 0:
# 			for point in allpoints_global:
# 				if point['sender'] == me.key and int(point['cluster']) == idx:
# 					full_balance += float(point['credit']) / 1e18
# 	return round(full_balance, 2), chain_balance

def getBalance_global():
	#check all my balance, including those frozen in unverified clusters.
	chain_balance  = balance_global
	full_balance   = chain_balance

	cluster_buffer = [0] * len(allclusters_global)
	for point in allpoints_global:
		i = int(point['cluster'])

		try:
			#allclusters_global[i]['verified'] == 0
			if point['sender'] == me.key and allclusters_global[i]['verified'] == 0:
				if cluster_buffer[i] == 0:
					full_balance += float(point['credit']) / 1e18
					cluster_buffer[i] = 1
		except:
			print(f'index error {i}')


	return round(full_balance, 2), chain_balance

_, key_to_id = mapping_id_keys("../../blockchain/keystores/", limit=200)
def call(show_points = True, raw = False):

	block    = lastblock_global
	points   = allpoints_global
	clusters = allclusters_global
	balance, usable  = getBalance_global()
	unclustered_points = []
	
	if not raw:
		for point in points:
			if point['cluster']>=0:
				p1 = point['position']
				p2 = clusters[point['cluster']]['position']
			point['RME'] = round(colourBGRDistance(p1,p2)/1e5, 2)
			point['MAN'] = round(manhattan_distance(p1,p2)/1e5, 2)
			point['CHS'] = round(chebyshev_distance(p1,p2)/1e5, 2)
			point['position'] = [round(i/1e5) for i in point['position']]
			point['credit'] //= 1e16
			# point['sender'] = point['sender'][0:5]
			point['sender'] = key_to_id[point['sender'].lower()]

		for idx, cluster in enumerate(clusters):
			del cluster['life']
			cluster['outlier_senders'] = len(cluster['outlier_senders'])
			cluster['position'] = [round(i/1e5) for i in cluster['position']]
			cluster['sup_position'] = [round(i/1e5) for i in cluster['sup_position']]
			cluster['total_credit'] //= 1e16
			cluster['total_credit_food'] //= 1e16
			cluster['total_credit_outlier'] //= 1e16
			# cluster['init_reporter'] = cluster['init_reporter'][0:5]
			cluster['init_reporter'] = key_to_id[cluster['init_reporter'].lower()]

			if show_points:
				cluster['points'] = [point for point in points if point['cluster']==idx]
				unclustered_points = [point for point in points if point['cluster']==-1]
	print_table(clusters)
	print()
	print(f"LAST BLOCK: block# (hash) {block['number']} ({block['hash'].hex()[0:8]})")
	print(f"MY BALANCE: usable (balance) {usable:.2f} ({balance:.2f})")
	if show_points:
		print_table(unclustered_points, indent = 2)

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

		START()
		mainlogger.info('Robot ID: %s (Byzantine)', me.id)

	elif sys.argv[1] == '--fau':

		START()
		mainlogger.info('Robot ID: %s (Faulty)', me.id)

	elif sys.argv[1] == '--nowalk':
		cwe.rot.setWalk(False)

		START()
		mainlogger.info('Robot ID: %s', me.id)

	elif sys.argv[1] == '--sandbox':
		print('---//--- SANDBOX-MODE ---//---')
		startFlag = True

mainlogger.info('Type Ctrl+C to stop experiment')
