#!/usr/bin/env python
from web3 import Web3, IPCProvider
from web3.middleware import geth_poa_middleware

def init_web3():
    w3 = Web3(IPCProvider('~/mygethnode/geth.ipc'))
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


