#!/usr/bin/env python
from web3 import Web3, IPCProvider
from web3.middleware import geth_poa_middleware
import os
import json

def init_web3():
    w3 = None

    w3 = Web3(IPCProvider('~/geth-pi-pucks/geth.ipc'))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    # self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    # w3.middleware_stack.inject(geth_poa_middleware, layer=0)
    w3.geth.personal.unlockAccount(w3.eth.coinbase,"",0)
    #w3.geth.personal.newAccount("")
    w3.eth.defaultAccount = w3.eth.coinbase
    key = w3.eth.coinbase
    enode = w3.geth.admin.nodeInfo().enode
    print('Welcome to the geth Python Console')
    print('Version:', w3.clientVersion)
    print('Your public address is:', key)
    print('Your enode is:', enode)

    return w3

def registerSC():
    global sc
    sc = None

    abiPath = os.getcwd()+'/scs/build/Estimation.abi'
    abi = json.loads(open(abiPath).read())

    addressPath = os.getcwd()+'/scs/contractAddress.txt'
    address = '0x'+open(addressPath).read().rstrip()

    sc = w3.eth.contract(abi=abi, address=address)


if __name__ == "__main__":

    w3 = init_web3()

