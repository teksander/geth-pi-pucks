#!/usr/bin/env python
from web3 import Web3, IPCProvider
from web3.middleware import geth_poa_middleware
import os
import sys
import subprocess
import json
from aux import TCP_server, Peer, colourBGRDistance, list2dict, print_table
import math, time
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
	w3.key = w3.eth.coinbase
	w3.enode = w3.geth.admin.nodeInfo().enode

	logger.info('VERSION: %s', w3.clientVersion)
	logger.info('ADDRESS: %s', w3.key)
	logger.info('ENODE: %s', w3.enode)

	return w3

def registerSC(w3):
    sc = None

    abiFile = '/home/pi/geth-pi-pucks/blockchain/scs/build/ForagingPtManagement.abi'
    abi = json.loads(open(abiFile).read())

    addressFile = '/home/pi/geth-pi-pucks/blockchain/scs/contractAddress.txt'
    address = '0x'+open(addressFile).read().rstrip()

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


def getBalance():
    # Return own balance in ether
    return round(w3.fromWei(w3.eth.getBalance(me.key), 'ether'), 2)

def getEnodes():
		return [peer.enode for peer in w3.geth.admin.peers()]

def getIds():
		return [readEnode(enode) for enode in getEnodes('geth')]

def call_clusters(sc, show = True):
	clusters = [list2dict(c, sc.functions.getClusterKeys().call()) for c in sc.functions.getClusters().call()]
	if show:
		print_table(clusters)
	return clusters 

def call_points(sc, show = True):
	points = [list2dict(c, sc.functions.getPointKeys().call()) for c in sc.functions.getPoints().call()]
	if show:
		print_table(points)
	return points

def call(sc, show_points = True, raw = False):

	clusters = call_clusters(sc, False)
	points   = call_points(sc, False)
	unclustered_points = []
	
	if not raw:

		for point in points:
			point['RME'] = round(colourBGRDistance(point['position'], clusters[point['cluster']]['position'])/1e5, 3)
			point['position'] = [round(i/1e5) for i in point['position']]
			point['credit'] //= 1e16
			point['sender'] = point['sender'][0:5]

		for idx, cluster in enumerate(clusters):
			del cluster['life']
			cluster['outlier_senders'] = len(cluster['outlier_senders'])
			cluster['position'] = [round(i/1e5) for i in cluster['position']]
			cluster['sup_position'] = [round(i/1e5) for i in cluster['sup_position']]
			cluster['total_credit'] //= 1e16
			cluster['total_credit_food'] //= 1e16
			cluster['total_credit_outlier'] //= 1e16
			cluster['init_reporter'] = cluster['init_reporter'][0:5]

			if show_points:
				cluster['points'] = [point for point in points if point['cluster']==idx]
				unclustered_points = [point for point in points if point['cluster']==-1]
	print_table(clusters)
	print()
	if show_points:
		print_table(unclustered_points, indent = 2)

if __name__ == "__main__":

	w3 = init_web3()
	sc = registerSC(w3)
	me = Peer(open("/boot/pi-puck_id", "r").read().strip(), w3.enode, w3.key)
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

			w3.geth.miner.start()