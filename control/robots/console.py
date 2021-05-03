#!/usr/bin/env python
from web3 import Web3, IPCProvider
from web3.middleware import geth_poa_middleware
import os
import json

def init_web3():
    w3 = Web3(IPCProvider('~/geth-pi-pucks/geth.ipc'))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    w3.geth.personal.unlockAccount(w3.eth.coinbase,'123456',0)
    w3.eth.defaultAccount = w3.eth.coinbase
    key = w3.eth.coinbase
    enode = w3.geth.admin.nodeInfo().enode
    print('Welcome to the geth Python Console')
    print('Version:', w3.clientVersion)
    print('Your public address is:', key)
    print('Your enode is:', enode)

    return w3

def registerSC():
    sc = None

    abiPath = os.getcwd()+'/scs/build/Estimation.abi'
    abi = json.loads(open(abiPath).read())

    addressPath = os.getcwd()+'/scs/contractAddress.txt'
    address = open(addressPath).read()

    sc = w3.eth.contract(abi=abi, address=address)
    return sc

if __name__ == "__main__":

    w3 = init_web3()

