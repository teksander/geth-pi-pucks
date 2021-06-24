#!/usr/bin/env python3
import time
import sys
import threading
import socket
import subprocess
import os
import logging

# The logs that go to console
logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')

# # The logs that go to a file (include debugging logs)
# fh = logging.FileHandler('logs/main.log','w')
# fh.setFormatter(logging.Formatter(logsFormat))
# fh.setLevel(10)
# logging.getLogger('').addHandler(fh)

logger = logging.getLogger(__name__)

class TicToc(object):
    """ Pendulum Class to Synchronize Output Timess
    """
    def __init__(self, delay, name = None):
        """ Constructor
        :type delay: float
        :param delay: Time to wait
        """         
        self.delay = delay      
        self.stime = time.time()  
        self.name = name

    def tic(self):
        self.stime = time.time()    

    def toc(self):
        dtime = time.time() - self.stime 
        if dtime < self.delay:
            time.sleep(self.delay - dtime)
        else:
            # logger.warning('{} Pendulum too Slow. Elapsed: {}'.format(self.name,dtime))
            pass

class TCP_server(object):
    """ Set up TCP_server on a background thread
    The __hosting() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(self, data, ip, port, unlocked = False):
        """ Constructor
        :type data: str
        :param data: Data to be sent back upon request
        :type ip: str
        :param ip: IP address to host TCP server at
        :type port: int
        :param port: TCP listening port for enodes
        """
        self.__stop = 1
        
        self.data = data
        self.ip = ip
        self.port = port                              
        self.newIds = set()
        self.allowed = set()
        self.unlocked = unlocked
        self.count = 0 # For debugging
        self.allowedCount = 0 # For debugging

        logger.info('TCP-Server OK')

    def __hosting(self):
        """ This method runs in the background until program is closed """ 
         # create a socket object
        __socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        # set important options
        __socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # get local machine name
        __host = socket.gethostbyname(self.ip)
        # bind to the port
        __socket.bind((__host, self.port))  

        logger.info('TCP Server OK')  

        while True:
            try:
                # set the timeout
                __socket.settimeout(5)
                # queue one request
                __socket.listen(1)    
                # establish a connection
                __clientsocket,addr = __socket.accept()   
                logger.debug("TCP request from %s" % str(addr))
                self.count += 1

                if (addr[0][-3:] in self.allowed) or self.unlocked:
                    __clientsocket.send(self.data.encode('ascii'))
                    self.unallow(addr[0][-3:])
                    self.allowedCount += 1

                __clientsocket.close()

                # make of set of connection IDs
                newId = str(addr[0]).split('.')[-1]
                self.newIds.add(newId)

            except socket.timeout:
                pass

            time.sleep(0.5)

            if self.__stop:
                __socket.close()
                break 

    def request(self, server_ip, port):
        """ This method is used to request data from a running TCP server """
        # create the client socket
        __socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        # set the connection timeout
        __socket.settimeout(5)
        # connect to hostname on the port
        __socket.connect((server_ip, port))                               
        # Receive no more than 1024 bytes
        msg = __socket.recv(1024)  
        msg = msg.decode('ascii') 

        if msg == '':
            raise ValueError('Connection Refused')

        __socket.close()   
        return msg

        return 

    def lock(self):
        self.unlocked = False
    def unlock(self):
        self.unlocked = True

    def allow(self, client_ids):
        for client_id in client_ids:
            self.allowed.add(client_id)

    def unallow(self, client_ids):
        for client_id in client_ids:
            self.allowed.discard(client_id)

    def getNew(self):
        if self.__stop:
            return set()
            logger.warning('getNew: TCP is OFF')

        temp = self.newIds
        self.newIds = set()
        return temp

    def start(self):
        """ This method is called to start __hosting a TCP server """
        if self.__stop:
            self.__stop = 0
            # Initialize background daemon thread
            thread = threading.Thread(target=self.__hosting, args=())
            thread.daemon = True 

            # Start the execution                         
            thread.start()   
        else:
            logger.warning('TCP Server already ON')  

    def stop(self):
        """ This method is called before a clean exit """   
        self.__stop = 1
        logger.info('TCP Server OFF') 



class Peer(object):
    """ Establish the Peer class 
    """
    def __init__(self, id__, enode = None, key = None):
        """ Constructor
        :type id__: str
        :param id__: id of the peer
        """
        # Add the known peer details
        self.id = id__
        self.ip = '172.27.1.' + id__
        self.tStamp = time.time()
        self.enode = enode
        self.key = key
        # self.ageLimit = ageLimit
        self.isDead = False
        self.age = 0
        self.trials = 0
        self.timeout = 0
        self.timeoutStamp = 0

    def resetAge(self):
        """ This method resets the timestamp of the robot meeting """ 
        self.tStamp = time.time()

    def kill(self):
        """ This method sets a flag which identifies aged out peers """
        self.isDead = True

    def setTimeout(self, timeout = 10):
        """ This method resets the timestamp of the robot timing out """ 
        self.trials = 0
        self.timeout = timeout
        self.timeoutStamp = time.time()

class PeerBuffer(object):
    """ Establish the Peer class 
    """
    def __init__(self, ageLimit = 2):
        """ Constructor
        :type id__: str
        :param id__: id of the peer
        """
        # Add the known peer details
        self.buffer = []
        self.ageLimit = ageLimit
        self.__stop = True

    def aging(self):
        """ This method runs in the background until program is closed 
        self.age is the time elapsed since the robots meeting.
        """            
        # while True:
        # Age each peer in the buffer
        for peer in self.buffer:
            peer.age = time.time() - peer.tStamp

            if peer.age > self.ageLimit:
                peer.kill()

            if peer.timeout != 0:
                if (peer.timeout - (time.time() - peer.timeoutStamp)) <= 0:
                    peer.timeout = 0      

    def __aging(self):
        """ This method runs in the background until program is closed 
        self.age is the time elapsed since the robots meeting.
        """            
        while True:
            # Age each peer in the buffer
            for peer in self.buffer:
                peer.age = time.time() - peer.tStamp

                if peer.age > self.ageLimit:
                    peer.kill()

                if peer.timeout != 0:
                    if (peer.timeout - (time.time() - peer.timeoutStamp)) <= 0:
                        peer.timeout = 0      

            if self.__stop:
                break
            else:
                time.sleep(0.05);   

    def addPeer(self, newIds):
        """ This method is called to add a peer Id
            newPeer is the new peer object
        """   
        for newId in newIds:
            if newId not in self.getIds():
                newPeer = Peer(newId)  
                self.buffer.append(newPeer)
            else:
                self.getPeerById(newId).resetAge()

    def removePeer(self, oldId):
        """ This method is called to remove a peer Id
            newPeer is the new peer object
        """   
        self.buffer.pop(self.getIds().index(oldId))

    def getIds(self): 
        return [peer.id for peer in self.buffer]
    def getAges(self):
        return [peer.age for peer in self.buffer]
    def getEnodes(self):
        return [peer.enode for peer in self.buffer]
    def getIps(self):
        return [peer.ip for peer in self.buffer]       
    def getkeys(self):
        return [peer.key for peer in self.buffer]

    def getPeerById(self, id):
        return self.buffer[self.getIds().index(id)]

    def getPeerByEnode(self, enode):
        return self.buffer[self.getEnodes().index(enode)]

    def start(self,):
        """ This method is called to start calculating peer ages"""
        if self.__stop:  
            self.__stop = False

            # Initialize background daemon thread
            self.thread = threading.Thread(target=self.__aging, args=())
            self.thread.daemon = True   
            # Start the execution                         
            self.thread.start()   

    def stop(self):
        """ This method is called before a clean exit """   
        self.__stop = True
        self.thread.join()
        logger.info('Peer aging stopped') 

class Logger(object):
    """ Logging Class to Record Data to a File
    """
    def __init__(self, logfile, header, rate = 0):

        self.file = open(logfile, 'w+')
        self.rate = rate
        self.tStamp = 0
        self.tStart = 0
        pHeader = ' '.join([str(x) for x in header])
        self.file.write('{} {} {}\n'.format('ID', 'TIME', pHeader))
        self.id = open("/boot/pi-puck_id", "r").read().strip()

    def log(self, data):
        """ Method to log row of data
        :param data: row of data to log
        :type data: list
        """ 
        
        if self.isReady():
            self.tStamp = time.time()
            try:
                tString = str(round(self.tStamp-self.tStart, 3))
                pData = ' '.join([str(x) for x in data])
                self.file.write('{} {} {}\n'.format(self.id, tString, pData))
            except:
                pass
                logger.warning('Failed to log data to file')

    def isReady(self):
        return time.time()-self.tStamp > self.rate

    def start(self):
        self.tStart = time.time()

    def close(self):
        self.file.close()

def readEnode(enode, output = 'id'):
    # Read IP or ID from an enode
    ip_ = enode.split('@',2)[1].split(':',2)[0]

    if output == 'ip':
        return ip_
    elif output == 'id':
        return ip_.split('.')[-1] 

def getCPUPercent():
    return str(round(float(os.popen('''grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage }' ''').readline()),2))

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

