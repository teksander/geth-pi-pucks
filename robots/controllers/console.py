#!/usr/bin/env python
from web3 import Web3, IPCProvider
from web3.middleware import geth_poa_middleware
import os
import sys
import subprocess
import json
from aux import TCP_server, Peer, list2dict, print_dict
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
	w3.key = w3.eth.coinbase
	w3.enode = w3.geth.admin.nodeInfo().enode

	logger.info('VERSION: %s', w3.clientVersion)
	logger.info('ADDRESS: %s', w3.key)
	logger.info('ENODE: %s', w3.enode)

	return w3

def registerSC(w3):
    sc = None

    abiFile = '../scs/build/ForagingPtManagement.abi'
    abi = json.loads(open(abiFile).read())

    addressFile = '../scs/contractAddress.txt'
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

def rgb_to_ansi(rgb):
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m"

def print_table(data, indent = 0, header = True):
    if not data:
        return

    # Get the field names from the first dictionary in the list
    field_names = list(data[0].keys())

    # Calculate the maximum width of each column
    column_widths = {}
    for name in field_names:
        column_widths[name] = max(len(str(row.get(name, ""))) for row in data) + 2

    # Print the table header
    if header:
        for name, width in column_widths.items():
            print(indent*"  " + name + '  ', end="")
        print()

    # Print the table rows
    for row in data:
        ansi_code = rgb_to_ansi(row['position'])
        print("\n" + indent*"  " + bool(indent)*"*", end="")
        for name, width in column_widths.items():
            if isinstance(row.get(name, ""), list) and all(isinstance(item, dict) for item in row.get(name, "")):
                print_table(row.get(name, ""), indent=1, header=False)
            else:
                value = str(row.get(name, ""))
                print(ansi_code + value.ljust(width) + "\033[0m", end="")

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