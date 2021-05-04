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
import smbus

global startFlag
global isbyz
startFlag = 0
isbyz = 0

# /* Experiment Parameters */
#######################################################################
tcpPort = 40421 
erbDist = 175
gsFreq = 2
rwSpeed = 500
pcID = '100'

estimateRate = 1
voteRate = 45
bufferRate = 0.5
eventRate = 1
globalPeers = 0
ageLimit = 2

# Global parameters
# subprocess.call("source ../../globalconfig")

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
		self.tStamp = 0
		self.tStart = 0
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
				tString = str(round(self.tStamp-self.tStart, 3))
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

mainheader = ['EVENT DESCRIPTION']
mainlog = Logger('logs/main.txt', mainheader)

estimateheader = ['ESTIMATE','W','B','S1','S2','S3']
estimatelog = Logger('logs/estimate.csv', estimateheader)

bufferheader = ['#BUFFER', '#GETH','#ALLOWED', 'BUFFERPEERS', 'GETHPEERS','ALLOWED']
bufferlog = Logger('logs/buffer.csv', bufferheader, 2)

voteheader = ['VOTE']
votelog = Logger('logs/vote.csv', voteheader)

blockheader = ['TELAPSED','TIMESTAMP','BLOCK', 'HASH', 'PHASH', 'DIFF', 'TDIFF', 'SIZE','TXS', 'UNC']
blocklog = Logger('logs/block.csv', blockheader)

scheader = ['BLOCK', 'BALANCE', 'UBI', 'PAY','#ROBOT', 'MEAN', '#VOTES','#OKVOTES', 'R?','C?']
sclog = Logger('logs/sc.csv', scheader)

syncheader = ['#BLOCKS']
synclog = Logger('logs/sync.csv', syncheader)

extraheader = ['CHAINDATASIZE', '%CPU']
extralog = Logger('logs/extra.csv', extraheader)

# Edit logmodules list to include the desired logs
logmodules = [bufferlog, estimatelog, votelog, sclog, mainlog, blocklog, synclog, extralog]

# /* Define Main-modules */
#######################################################################

def Estimate(rate = estimateRate):
	""" Control routine to update the local estimate of the robot """
	global estimate
	estimate = 0
	totalWhite = 0
	totalBlack = 0

	while True:
		if not startFlag:
			print('Stopped Estimating')
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
	global peerBuffer
	peerBuffer = []
	
	def globalBuffer():
		peerFile = open('pi-pucks.txt', 'r') 
		tcp.unlock()

		for newId in peerFile:
			newId = newId.strip()
			if newId not in getIds():
				newPeer = Peer(newId)
				newPeer.w3 = w3
				peerBuffer.append(newPeer)

		for peer in peerBuffer: 
			if not getIds('geth'):
				try:
					peer.enode = tcp.request(newPeer.ip, tcp.port)
				except:
					pass

		peerFile.close()

	def localBuffer():
		# Broadcast own ID to E-RANDB
		erb.transmit(me.id)

		# Collect new peer IDs from E-RANDB and TCP
		for newId in erb.getNew():
			tcp.allow(newId)
			if newId not in getIds():
				newPeer = Peer(newId)
				newPeer.w3 = w3
				newPeer.ageLimit = ageLimit
				peerBuffer.append(newPeer)
				# mainlog.log(['Added {} to buffer'.format(newPeer.id)])
			else:
				peerBuffer[getIds().index(newId)].reset_age()

		# Perform Buffering tasks for each peer in the buffer
		for peer in peerBuffer:

			# If the peer has died (aged out); Remove from buffer
			if peer.isdead:
				mainlog.log(['Killed {} @ age {:.2f}'.format(peer.id, peer.age)])
				peerBuffer.pop(getIds().index(peer.id))
				tcp.unallow(peer.id)
				continue

			# If the peer connection times out; Kill and remove from buffer
			elif peer.age > 3:
				peer.isdead = True
				peerBuffer.pop(getIds().index(peer.id))
				tcp.unallow(peer.id)
				continue
				# mainlog.log(['Peer {} connection failed'.format(peer.id)])

			# If the peer enode is still unknown; make TCP request
			elif peer.enode == None:
				try:
					peer.enode = tcp.request(peer.ip, tcp.port)
					rw.setLEDs(0b11111111)  
					mainlog.log(['Received {} enode'.format(peer.id)]) 	   		 
				except ValueError:
					pass
					# print('Peer Refused Connection')
				except:
					pass
					# print('Peering Failed')

		if not peerBuffer:
			rw.setLEDs(0b00000000)	

		if bufferlog.isReady():
			gethIds = getIds('geth')
			bufferIds = getIds('buffer')
			bufferlog.log([len(gethIds), len(bufferIds), len(tcp.allowed), ';'.join(bufferIds), ';'.join(gethIds), ';'.join(tcp.allowed)])


	while True:
		if not startFlag:
			print('Stopped Buffering')
			break

		tic = TicToc(rate, 'Buffer')
		
		if globalPeers:
			globalBuffer()
		else:
			localBuffer()

		tic.toc()

	
def Vote(rate = voteRate):
	""" Control routine to broadcast current estimate to the blockchain """
	ticketPrice = sc.functions.getTicketPrice().call()

	def sendVote():
		vote = int(estimate*1e7)
		voteHash = sc.functions.sendVote(vote).transact({'from': me.key,'value': w3.toWei(ticketPrice,'ether')})
		voteReceipt = w3.eth.waitForTransactionReceipt(voteHash)
		return voteReceipt

	time.sleep(rate)
	while True:
		if not startFlag:
			print('Stopped Voting')
			break

		tic = TicToc(rate, 'Vote')


		while True:
			try:
				vote = int(estimate*1e7)
				voteHash = sc.functions.sendVote(vote).transact({'from': me.key,'value': w3.toWei(ticketPrice,'ether')})
				voteReceipt = w3.eth.waitForTransactionReceipt(voteHash)

				mainlog.log(['Voted: {}; Status: {}'.format(estimate, voteReceipt.status)])
				votelog.log([vote])
				rgb.flashGreen()
				break

			except ValueError:
				mainlog.log(['Failed Vote (No Balance). Balance: {}'.format(getBalance())])
				votelog.log([None])
				rgb.flashRed()
				break

			except:
				mainlog.log(['Failed Vote (Unexpected). Trying again. Balance: {}'.format(getBalance())])
	

		# Low frequency logging of chaindata size and cpu usage
		chainSize = getFolderSize('/home/pi/geth-pi-pucks/geth')
		useCPU = str(round(float(os.popen('''grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage }' ''').readline()),2))
		extralog.log([chainSize,useCPU])

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
		ubi = sc.functions.askForUBI().call()
		payout = sc.functions.askForPayout().call()
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
			print('Stopped Events')
			break

		tic = TicToc(rate, 'Event')

		newBlocks = blockFilter.get_new_entries()
		if newBlocks:
			synclog.log([len(newBlocks)])

			for blockHex in newBlocks:
				blockHandle()

			if ubi != 0:
				sc.functions.askForUBI().transact()

			if payout != 0:
				sc.functions.askForPayout().transact()

			try:
				if newRound:
					sc.functions.updateMean().transact()
			except:
				pass

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
	print('Starting Experiment')
	global startFlag
	for log in logs:
		try:
			log.start()
		except:
			print('Error Starting Log')

	startFlag = 1 
	for module in modules:
		try:
			module.start()
		except:
			print('Error Starting Module')

	mainlog.log(['STARTED EXPERIMENT'])

def signal_handler(sig, frame):

	def STOP(modules = submodules, logs = logmodules):
		print('Ctrl+C pressed. Stopping...')
		global startFlag

		mainlog.log(['STOPPED EXPERIMENT'])
		print('--/-- Stopping Main-modules --/--')
		startFlag = 0
		time.sleep(1)

		print('--/-- Stopping Sub-modules --/--')
		for submodule in modules:
			try:
				submodule.stop()
			except:
				print('Error Stopping Module')

		for log in logs:
			try:
				log.close()
			except:
				print('Error Closing Logfile')
				
		if isbyz:
			print('This Robot Is BYZANTINE')

	if not startFlag:
		START()
	elif startFlag:
		STOP()


signal.signal(signal.SIGINT, signal_handler)	

# /* Some useful functions */
#######################################################################

def getBalance():
    # Return own balance in ether
    return round(w3.fromWei(w3.eth.getBalance(me.key), 'ether'), 2)

def readEnode(enode, output = 'id'):
	# Read IP or ID from an enode
	ip_ = enode.split('@',2)[1].split(':',2)[0]

	if output == 'ip':
		return ip_
	elif output == 'id':
		return ip_.split('.')[-1] 

def getEnodes(database='buffer'):
	if database == 'buffer':
		return [peer.enode for peer in peerBuffer]
	elif database == 'geth':
		return [peer.enode for peer in w3.geth.admin.peers()]

def getIds(database='buffer'):
	if database == 'buffer':
		return [peer.id for peer in peerBuffer]
	elif database == 'geth':
		return [readEnode(enode) for enode in getEnodes('geth')]

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

# def waitForSC():
# 	global sc
# 	sc = None

# 	w3.geth.miner.start()
# 	txFilter = w3.eth.filter('pending')
# 	while True:
# 		for txHex in txFilter.get_new_entries():
# 			tx = w3.eth.getTransaction(txHex)
# 			if tx['to'] == None:
# 				scReceipt = w3.eth.waitForTransactionReceipt(tx.hash)
# 				abiPath = os.getcwd()+'/scs/build/Estimation.abi'
# 				abi = json.loads(open(abiPath).read())

# 				sc = w3.eth.contract(abi=abi, address=scReceipt.contractAddress)
# 				startBlock = scReceipt.blockNumber
# 				global startStamp
# 				startStamp = w3.eth.getBlock(startBlock).timestamp
# 				mainlog.log(['SETUP: Smart Contract Received at Block {}'.format(startBlock)])	
# 				print('Smart Contract Received at Block {}'.format(startBlock))
# 				break	

# 		if sc != None:
# 			sc.functions.registerRobot().transact()
# 			w3.geth.miner.stop()
# 			if globalPeers:
# 				break
# 			else:
# 				pc.w3 = w3
# 				pc.kill()
# 				if not pc.isPeer():
# 					break
# 		else:
# 			time.sleep(2)

def registerSC():
	sc = None

	abiPath = os.getcwd()+'/scs/build/Estimation.abi'
	abi = json.loads(open(abiPath).read())

	addressPath = os.getcwd()+'/scs/contractAddress.txt'
	address = '0x'+open(addressPath).read().rstrip()

	sc = w3.eth.contract(abi=abi, address=address)
	
	return sc

def i2cdetect():
	i2cFlag = True
	bus = smbus.SMBus(4) # 1 indicates /dev/i2c-1
	for device in [0x1f, 0x20, 0x60,0x6e]:
		try:
			bus.read_byte(device)
		except:
			print('I2C Bus not responding: {}'.format(device))
			i2cFlag = False

	return i2cFlag

# /* BEGIN EXPERIMENT */ 
#######################################################################

if len(sys.argv) == 1:
	#######################################################################
	# /* Check for I2C */ 
	print('Checking I2C Connections...')
	if i2cdetect():
		print('All I2C Devices OK')
	else:
		print('I2C Device Failed')

	# /* Wait for Time Synchronization */ 
	print('Waiting for Time Sync...')
	waitForTS()

	# /* Register to the Smart Contract*/
	sc = registerSC()
	if sc:
		sc.functions.registerRobot().transact()
	else:
		print('SC Register Failed')

	# # /* Wait for PC Enode */
	# print('Waiting for PC Enode...')
	# waitForPC()

	# # /* Wait for Smart Contract */
	# print('Waiting for SC deployment...')
	# waitForSC()


	# /* Begin Experiment */
	#######################################################################
	START()
	print('Type Ctrl+C to stop experiment')

elif len(sys.argv) == 2:

	if sys.argv[1] == '--sandbox':
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

	elif sys.argv[1] == '--i2cdetect':
		# /* Check for I2C */ 
		print('Checking I2C Connections...')
		if i2cdetect():
			print('All I2C Devices OK')
		else:
			print('I2C Device Failed')

	elif sys.argv[1] == '--byz':
		isbyz = 1

		# /* Requests to monitor PC (Centralized Bit) */
		#######################################################################
		# /* Check for I2C */ 
		print('Checking I2C Connections...')
		if i2cdetect():
			print('All I2C Devices OK')
		else:
			print('I2C DEVICE FAILED')

		# /* Wait for Time Synchronization */ 
		print('Waiting for Time Sync...')
		waitForTS()

		# /* Register to the Smart Contract*/
		sc = registerSC()
		if sc:
			sc.functions.registerRobot().transact()
		else:
			print('SC register failed')

		# # /* Wait for PC Enode */
		# print('Waiting for PC Enode...')
		# waitForPC()

		# # /* Wait for Smart Contract */
		# print('Waiting for SC deployment...')
		# waitForSC()

		START()
		print('Type Ctrl+C to stop experiment')
		print('This Robot Is BYZANTINE')