#!/usr/bin/env python3
# This is the main control loop running on the foreground in each robot
from console import *
import time
import sys
import os
import signal
import json
import threading
import subprocess
from erandb import ERANDB
from randomwalk import RandomWalk
from groundsensor import GroundSensor
from rgbleds import RGBLEDs
from aux import TicToc, TCP_server, Peer

global startFlag
global isbyz
startFlag = 0
isbyz = 0

blockCounter = 0
meetCounter = 0

# /* Experiment Parameters */
#######################################################################
tcpPort = 40421 
erbDist = 200
gsFreq = 2
rwSpeed = 500
pcID = '100'

estimateRate = 1
voteRate = 45
bufferRate = 0.33
eventRate = 1
globalPeers = 0
ageLimit = 2

# /* Initialize Sub-modules */
#######################################################################

# /* Init web3.py */
print('Booting Python Geth Console...')
w3 = init_web3()
# /* Init an instance of peer for this Pi-Puck */
myID  = open("/boot/pi-puck_id", "r").read().strip()
myEN  = w3.geth.admin.nodeInfo().enode
myKEY = w3.eth.coinbase
me = Peer(myID, myEN, myKEY)
# /* Init an instance of peer for the monitor PC */
pc = Peer(pcID)
# /* Init TCP server, __hosting process and request function */
print('Initialising TCP server...')
tcp = TCP_server(me.enode, me.ip, tcpPort)
# /* Init E-RANDB __listening process and transmit function
print('Initialising E-RANDB board...')
erb = ERANDB(erbDist)
# /* Init Ground-Sensors, __mapping process and vote function */
print('Initialising Ground-Sensors...')
gs = GroundSensor()
# /* Init Random-Walk, __walking process */
print('Initialising Random-Walk...')
rw = RandomWalk(rwSpeed)
# /* Init LEDs */
rgb = RGBLEDs()

submodules = [w3.geth.miner, tcp, erb, gs, rw]

# /* Initialize Logging Files */
#######################################################################

class Logger(object):
	""" Logging Class to Record Data to a File
	"""
	def __init__(self, logfile, header, rate = 0):

		self.file = open(logfile, 'w+')
		self.rate = rate
		self.tStamp = time.time()
		self.tStart = time.time()
		pHeader = ' '.join([str(x) for x in header])
		self.file.write('{} {} {} {}\n'.format('ID', 'TIME', 'BLK', pHeader))
	def log(self, data):
		""" Method to log row of data
		:type data: list
		:param data: row of data to log
		"""	
		
		if self.isReady():
			self.tStamp = time.time()
			try:
				tString = str(int((self.tStamp-self.tStart)*10))
				cBlock = w3.eth.getBlock('latest').number
				pData = ' '.join([str(x) for x in data])
				self.file.write('{} {} {} {}\n'.format(me.id, tString, cBlock, pData))
			except:
				mainlog.log(['File is closed'])

	def isReady(self):
		return time.time()-self.tStamp > self.rate

	def start(self):
		self.tStart = time.time()

	def close(self):
		self.file.close()

bufferheader = ['#BUFFER', '#GETH', 'BUFFERPEERS', 'GETHPEERS']
bufferlog = Logger('logs/buffer.log', bufferheader, 5)

# estimateheader = ['ESTIMATE','OPINION','S1','S2','S3']
estimateheader = ['ESTIMATE','W','B','S1','S2','S3']
estimatelog = Logger('logs/estimate.log', estimateheader)

eventheader = ['BLOCK', 'UBI', 'PAY', 'BALANCE','MEAN', '#VOTES','#OKVOTES', 'C?', 'BCSIZE', 'CPU']
eventlog = Logger('logs/event.log', eventheader)

voteheader = ['VOTE']
votelog = Logger('logs/vote.log', voteheader)

mainheader = ['DETAIL']
mainlog = Logger('logs/main.log', mainheader)

extraheader = ['#MEETS', '#BLOCKS']
extralog = Logger('logs/extra.log', extraheader, 60)

blockheader = ['BLOCK', 'HASH', 'PHASH', 'DIFF', 'TDIFF', 'SIZE','TXS', 'UNC']
blocklog = Logger('logs/block.log', blockheader)

logmodules = [bufferlog, estimatelog, votelog, eventlog, mainlog, extralog, blocklog]

# /* Define Main-modules */
#######################################################################

def Estimate(rate = estimateRate):
	""" Control routine to update the local estimate of the robot """
	global estimate
	estimate = 0
	totalWhite = 0
	totalBlack = 0

	while True:
		tic = TicToc(rate)

		# Set counters for grid colors
		newValues = gs.getAvg()

		if gs.hasFailed():
			print("GS error")
			estimatelog.log([None]) 
		elif newValues == None:
			estimatelog.log([None]) 
		else:
			for value in newValues:
				if value > 700:
					totalWhite += 1
				else:
					totalBlack += 1
			if isbyz:
				estimate = 0
			else:
				estimate = (0.5+totalWhite)/(totalWhite+totalBlack+1)

			estimatelog.log([round(estimate,3),totalWhite,totalBlack,newValues[0],newValues[1],newValues[2]]) 

		if not startFlag:
			print('Stopped Estimating')
			break
		else:
			tic.toc()

def Buffer(rate = bufferRate, ageLimit = ageLimit):
	""" Control routine for robot-to-robot dynamic peering """
	global blockCounter
	global peerBuffer
	global meetCounter
	peerBuffer = []

	peerFile = open('pi-pucks.txt') 

	def globalBuffer():
		for newId in peerFile:
			newId = newId.strip()
			if newId not in getIds():
				# Create a new peer thread; Request Enode;
				try:
					newPeer = Peer(newId)
					newPeer.enode = tcp.request(newPeer.ip, tcp.port)
					newPeer.w3 = w3   	   		 
					peerBuffer.append(newPeer)
				except:
					pass

	def localBuffer():
		global meetCounter
		# Broadcast own ID to E-RANDB
		erb.transmit(me.id)

		# Collect peer IDs from E-RANDB and TCP
		for newId in erb.getNew():
			# rw.flashLEDs(0.1)
			if newId not in getIds():
			# IF peer is not in buffer: create a new peer thread; Request Enode
				# print(newId)
				# rw.flashLEDs()
				meetCounter += 1
				try:
					newPeer = Peer(newId)
					newPeer.enode = tcp.request(newPeer.ip, tcp.port)
					newPeer.ageLimit = ageLimit
					newPeer.w3 = w3    	   		 
					peerBuffer.append(newPeer)
					mainlog.log(['Added {}'.format(newPeer.id)])
				except:
					print('Failed to add peer {} ({})'.format(newPeer.id,newPeer.ip))
			else:
			# IF peer is known: reset peer age						 						
				peerBuffer[getIds().index(newId)].reset_age()

		# Remove Aged Out Peer from the Buffer
		for peer in peerBuffer:
			if peer.isdead:
				mainlog.log(['Killed {} @ age {:.2f}'.format(peer.id, peer.age)])
				peerBuffer.pop(getIds().index(peer.id))
		
		if peerBuffer:
			rw.setLEDs(0b11111111)
		else:
			rw.setLEDs(0b00000000)	


	while True:
		tic = TicToc(rate)
		
		if globalPeers:
			globalBuffer()
		else:
			localBuffer()

		# Log Peers once
		if bufferlog.isReady():
			gethPeers = getIds('geth')
			bufferPeers = getIds('buffer')
			bufferlog.log([len(bufferPeers), len(gethPeers), str(bufferPeers), str(gethPeers)]) 

		if extralog.isReady():
			extralog.log([meetCounter, blockCounter])
			meetCounter = 0
			blockCounter = 0
		
		if not startFlag:
			print('Stopped Peering')
			break
		else:
			tic.toc()

	
def Vote(rate = voteRate):
	""" Control routine to broadcast current estimate to the blockchain """

	def sendVote(_estimate):
		vote = int(_estimate*1e7)
		ticketPrice = sc.functions.getTicketPrice().call()
		voteHash = sc.functions.sendVote(vote).transact({'from': me.key,'value': w3.toWei(ticketPrice,'ether')})
		voteReceipt = w3.eth.waitForTransactionReceipt(voteHash)
		return voteReceipt

	time.sleep(rate)		
	while True:
		tic = TicToc(rate)

		if gs.hasFailed():
			gs.stop()
			gs.start()
			mainlog.log(['Failed Vote: GS Fail'])
			votelog.log([None])
			rgb.flashRed()

		else:
			try:
				voteReceipt = sendVote(estimate)
				if not voteReceipt.status:
					mainlog.log(['Failed Vote Status. Balance: {}'.format(getBalance())])
					votelog.log([None])
					rgb.flashRed()
				else:
					mainlog.log(['Voted: {}'.format(estimate)])
					votelog.log([vote])
					rgb.flashGreen()

			except:
				mainlog.log(['Failed Vote. Balance: {}'.format(getBalance())])
				votelog.log([None])
				rgb.flashRed()

		if not startFlag:
			print('Stopped Voting')
			break
		else:
			tic.toc()

def Event(rate = eventRate):
	""" Control routine to perform tasks triggered by an event """
	global blockCounter

    # sc.events.your_event_name.createFilter(fromBlock=block, toBlock=block, argument_filters={"arg1": "value"}, topics=[])
	blockFilter = w3.eth.filter('latest')

	def blockHandle():
		""" Tasks when a new block is added to the chain """

		# 1) Log relevant block data 
		block = w3.eth.getBlock(blockHex)
		balance = getBalance()
		ubi = sc.functions.askForUBI().call()
		payout = sc.functions.askForPayout().call()
		mean = sc.functions.getMean().call()
		voteCount = sc.functions.getVoteCount().call()
		voteOkCount = sc.functions.getVoteOkCount().call()
		consensus = sc.functions.isConverged().call()
		chainSize = getFolderSize('/home/pi/mygethnode/geth')
		useCPU = str(round(float(os.popen('''grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage }' ''').readline()),2))

		eventlog.log([block.number, ubi, payout, balance, mean, voteCount, voteOkCount, consensus, chainSize, useCPU])
		blocklog.log([block.number, block.hash.hex(), block.parentHash.hex(), block.difficulty, block.totalDifficulty, block.size, len(block.transactions), len(block.uncles)])

		# 2) Send LED signals 
		rgb.flashWhite()
		if consensus == 1:
			rgb.setLED([0x00,0x01,0x02], [0x02,0x02,0x02])
			rgb.freeze = True


	while True:
		tic = TicToc(rate)

		for enode in getDiff():
			cmd = "admin.removePeer(\"{}\")".format(enode)
			subprocess.call(["geth","--exec",cmd,"attach","/home/pi/mygethnode/geth.ipc"], stdout=subprocess.DEVNULL)   


		newBlocks = blockFilter.get_new_entries()

		if newBlocks:
			try:
				if sc.functions.askForUBI().call() != 0:
					sc.functions.askForUBI().transact()
			except:
				print('Failed to request UBI')

			try:
				if sc.functions.askForPayout().call() != 0:
					sc.functions.askForPayout().transact()
			except:
				print('Failed to request payout')

			try:
				if sc.functions.isNewRound().call():
					sc.functions.updateMean().transact()
			except:
				print('Failed to request mean update')

			for blockHex in newBlocks:
				blockCounter += 1
				blockHandle()

		if not startFlag:
			print('Stopped Events')
			break
		else:
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

def signal_handler(sig, frame):

	def START(modules = submodules + mainmodules, logs = logmodules):
		print('Ctrl+C pressed. Starting...')
		global startFlag
		startFlag = 1 
		mainlog.log(['STARTED EXPERIMENT'])
		for module in modules:
			try:
				module.start()
			except:
				print('Error Starting Module')

		for log in logs:
			try:
				log.start()
			except:
				print('Error Starting Log')

	def STOP(modules = submodules, logs = logmodules):
		print('Ctrl+C pressed. Stopping...')
		global startFlag
		startFlag = 0
		mainlog.log(['STOPPED EXPERIMENT'])

		for module in modules:
			try:
				module.stop()
			except:
				print('Error Stopping Module')

		for log in logs:
			try:
				log.close()
			except:
				print('Error Closing Logfile')

	if not startFlag:
		START()
	elif startFlag:
		STOP()
		
		if len(sys.argv) == 3:
			if sys.argv[1] == '--experiment':
				experimentName = sys.argv[2]
				os.system('./upload-logs "%s"' % (experimentName) )


signal.signal(signal.SIGINT, signal_handler)	

# /* Some useful functions */
#######################################################################

def getBalance():
    # Return own balance in ether
    return round(w3.fromWei(w3.eth.getBalance(me.key), 'ether'), 2)

def getEnodes(database='buffer'):
	if database == 'buffer':
		return [peer.enode for peer in peerBuffer]
	elif database == 'geth':
		return [peer.enode for peer in w3.geth.admin.peers()]

def getIds(database='buffer'):
	if database == 'buffer':
		return [peer.id for peer in peerBuffer]
	elif database == 'geth':
		return [enode.split('@',2)[1].split(':',2)[0].split('.')[-1] for enode in getEnodes('geth')]

def getAges():
	return [peer.age for peer in peerBuffer]
	
def getDiff():
	# Return peers from Geth which are NOT in buffer
	return set(getEnodes('geth'))-set(getEnodes('buffer'))-{me.enode}

def getFolderSize(folder):
	# Return the size of a folder
    total_size = os.path.getsize(folder)
    for item in os.listdir(folder):
        itempath = os.path.join(folder, item)
        if os.path.isfile(itempath):
            total_size += os.path.getsize(itempath)
        elif os.path.isdir(itempath):
            total_size += getFolderSize(itempath)
    return total_size

def uploadLogs(dir):
	# TODO Pythonic way to upload logs
	pass


def waitForTS():
	while True:
		try:
			TIME = tcp.request(pc.ip, 40123)
			subprocess.call(["sudo","timedatectl","set-time",TIME])
			mainlog.log(['SETUP: Synced Time'])
			print('Synced Time')
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
			print('Peered to PC')
			break
		except:
			time.sleep(1)

def waitForSC():
	global sc
	sc = None

	w3.geth.miner.start()
	txFilter = w3.eth.filter('pending')
	while True:
		for txHex in txFilter.get_new_entries():
			tx = w3.eth.getTransaction(txHex)
			if tx['to'] == None:
				scReceipt = w3.eth.waitForTransactionReceipt(tx.hash)
				abiPath = '/home/pi/mygethnode/control/experiment/scs/build/Estimation.abi'
				abi = json.loads(open(abiPath).read())

				sc = w3.eth.contract(abi=abi, address=scReceipt.contractAddress)
				startBlock = scReceipt.blockNumber
				mainlog.log(['SETUP: Smart Contract Received at Block {}'.format(startBlock)])	
				print('Smart Contract Received at Block {}'.format(startBlock))
				break	

		if sc != None:
			sc.functions.registerRobot().transact()
			w3.geth.miner.stop()
			if globalPeers:
				break
			else:
				pc.w3 = w3
				pc.kill()
				if not pc.isPeer():
					break
		else:
			time.sleep(2)


# /* BEGIN EXPERIMENT */ 
#######################################################################

if len(sys.argv) == 1:
	# /* Requests to monitor PC (Centralized Bit) */
	#######################################################################

	# /* Wait for Time Synchronization */ 
	print('Waiting for Time Sync...')
	waitForTS()

	# /* Wait for PC Enode */
	print('Waiting for PC Enode...')
	waitForPC()

	# /* Wait for Smart Contract */
	print('Waiting for SC deployment...')
	waitForSC()


	# /* Actually begin */
	#######################################################################
	print('Type Ctrl+C to begin experiment')

elif len(sys.argv) == 2:

	if sys.argv[1] == '--sandbox':
		print('---//--- SANDBOX-MODE ---//---')		
		startFlag = 1	

	elif sys.argv[1] == '--synctime':
		print('---//--- SYNC-TIME ---//---')
		# /* Wait for Time Synchronization */ 
		waitForTS()

	elif sys.argv[1] == '--peer2pc':
		print('---//--- SYNC-TIME ---//---')
		# /* Wait for Time Synchronization */ 
		waitForPC()
		startFlag = 1	

