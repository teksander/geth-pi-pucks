#!/usr/bin/env python
from web3 import Web3, IPCProvider
from web3.middleware import geth_poa_middleware
import os
import sys
import subprocess
import json
from aux import TCP_server, Peer
import time
import logging

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

def init_web3():
	w3 = None

	provider = IPCProvider('~/geth-pi-pucks/blockchain/geth.ipc')

	w3 = Web3(provider)
	w3.provider = provider
	w3.middleware_onion.inject(geth_poa_middleware, layer=0)
	w3.geth.personal.unlockAccount(w3.eth.coinbase,"",0)
	w3.eth.defaultAccount = w3.eth.coinbase
	key = w3.eth.coinbase
	enode = w3.geth.admin.nodeInfo().enode

	logger.info('VERSION: %s', w3.clientVersion)
	logger.info('ADDRESS: %s', key)
	logger.info('ENODE: %s', enode)

	return w3

def registerSC(w3):
    sc = None

    abiPath = os.path.dirname(os.getcwd())+'/scs/build/ForagingPtManagement.abi'
    abi = json.loads(open(abiPath).read())

    addressPath = os.path.dirname(os.getcwd())+'/scs/contractAddress.txt'
    address = '0x'+open(addressPath).read().rstrip()

    sc = w3.eth.contract(abi=abi, address=address)
    return sc

def waitForPC():
	while True:
		try:
			pc.enode = tcp.request(pc.ip, tcp.port)
			pc.key = tcp.request(pc.ip, 40422)
			w3.geth.admin.addPeer(pc.enode)
			# print('Peered to PC')
			break
		except:
			time.sleep(0.5)

def globalBuffer():
	peerFile = open('pi-pucks.txt', 'r') 
	
	for newId in peerFile:
		newId = newId.strip()
		if newId not in [peer.id for peer in peerBuffer]:
			newPeer = Peer(newId)
			newPeer.w3 = w3
			peerBuffer.append(newPeer)

	for peer in peerBuffer:
		while True:
			try:
				peer.enode = tcp.request(peer.ip, tcp.port)
				w3.geth.admin.addPeer(peer.enode)
				print('Peered to', peer.id)
				break
			except:
				time.sleep(0.5)
				
def waitForTS():
	while True:
		try:
			TIME = tcp.request(pc.ip, 40123)
			subprocess.call(["sudo","timedatectl","set-time",TIME])
			print('Synced Time')
			break
		except:
			time.sleep(1)

def getBalance():
    # Return own balance in ether
    return round(w3.fromWei(w3.eth.getBalance(me.key), 'ether'), 2)

def getEnodes():
		return [peer.enode for peer in w3.geth.admin.peers()]

def getIds():
		return [readEnode(enode) for enode in getEnodes('geth')]
	

if __name__ == "__main__":

	w3 = init_web3()
	myID  = open("/boot/pi-puck_id", "r").read().strip()
	myEN  = w3.geth.admin.nodeInfo().enode
	myKEY = w3.eth.coinbase
	me = Peer(myID, myEN, myKEY)
	pc = Peer('100')
	

	if len(sys.argv) >= 2:
		if sys.argv[1] == '--mine':

			tcpPort = 40421 
			tcp = TCP_server(me.enode, me.ip, tcpPort)
			tcp.start()
			tcp.unlock()

			peerBuffer = []
			# globalBuffer()
			waitForPC()
			waitForTS()

			w3.geth.miner.start()