#!/usr/bin/env python
import sys
sys.path.insert(1, '/home/volker/geth-pi-pucks/control/robots')
from console import *
from aux import TCP_server
import json
import os
import threading
import time
import socket
import logging

logging.basicConfig(format='[%(levelname)s %(name)s] %(message)s')
logger = logging.getLogger('console-pc')

logging.getLogger('console').setLevel(logging.INFO)
logger.setLevel(logging.INFO)


# /* FUNCTIONS */ 
#######################################################################

def getEnodes():
    return [peer.enode for peer in w3.geth.admin.peers()]

def getIds(database = 'geth'):
    if database == 'geth':
        return [enode.split('@',2)[1].split(':',2)[0].split('.')[-1] for enode in getEnodes()]

    elif database == 'file':
        keyMap = open('/home/eksander/geth-pi-pucks/control/monitor-pc/key-mapping.txt')
        return [line.split()[0] for line in keyMap]

def getIps(database = 'geth'):
    if database == 'geth':
        return [enode.split('@',2)[1].split(':',2)[0].split('.')[-1] for enode in getEnodes()]

def getKeys(database = 'file'):
    keyMap = open('/home/eksander/geth-pi-pucks/control/monitor-pc/key-mapping.txt')
    return [line.split()[-1] for line in keyMap]


def getBalances():
    for key in getKeys:
        address = w3.toChecksumAddress(key)
        print(key, round(w3.fromWei(w3.eth.getBalance(address), 'ether'), 2))

def fundRobots(value = 0.01):
    for key in getKeys:
        address = w3.toChecksumAddress(key)
        w3.eth.sendTransaction({'to': address, 'from': w3.eth.coinbase,'value': w3.toWei(value, 'ether')})

def deploySC():
    fundRobots()
    # Set path to build files
    abi_path = '/home/eksander/geth-pi-pucks/control/robots/scs/build/Estimation.abi'
    bin_path = '/home/eksander/geth-pi-pucks/control/robots/scs/build/Estimation.bin'

    # Load build files
    abi = json.loads(open(abi_path).read())
    bytecode = open(bin_path).read()
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Deploy smart contract
    txHash = contract.constructor().transact()
    txReceipt = w3.eth.waitForTransactionReceipt(txHash)
    print('Your Smart Contract was included in block', txReceipt.blockNumber,'\nAddress:', txReceipt.contractAddress,'\nCost:', txReceipt.gasUsed,'gas') 

    global startBlock 
    startBlock = txReceipt.blockNumber
    print(txReceipt.contractAddress)
    contract = w3.eth.contract(address=txReceipt.contractAddress, abi=abi)
    txUBIFunds = {'from': w3.eth.coinbase,'value': w3.toWei(10000,'ether')}
    contract.functions.sendFund().transact(txUBIFunds)
    print('Start Block:', contract.functions.startBlock().call())
    return contract

def registerSCPC():
    sc = None

    abiPath = '/home/eksander/geth-pi-pucks/control/robots/scs/build/Estimation.abi'
    addressPath = '/home/eksander/geth-pi-pucks/control/robots/scs/contractAddress.txt'

    abi = json.loads(open(abiPath).read())
    address = '0x'+open(addressPath).read()
    print(address)
    sc = w3.eth.contract(abi=abi, address=address)

    return sc


# /* BOOT CONSOLE */ 
#######################################################################

myIP  = '172.27.1.100'

try:
    w3 = init_web3()

    myENODE = w3.geth.admin.nodeInfo().enode
    myKEY = w3.eth.coinbase

    tcpENODE = TCP_server(myENODE, myIP, 40421, True)
    tcpKEY = TCP_server(myKEY, myIP, 40422, True)

    tcpENODE.start()
    tcpKEY.start()

except Exception as e:
    print(e)
    logger.info('No connection to Geth process')



myTIME = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
tcpTIME  = TCP_server(myTIME, myIP, 40123, True)

def clock():
    while True:
        myTIME = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        tcpTIME.data = myTIME
        time.sleep(0.5)


# Initialize background daemon thread
clockTh = threading.Thread(target=clock, args=())
clockTh.daemon = True   
clockTh.start()

tcpTIME.start()



