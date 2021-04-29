#!/usr/bin/env python3
import time
import sys
import threading
import socket
import subprocess

class TicToc(object):
    """ Pendulum Class to Synchronize Output Times
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
            # print('{} Pendulum too Slow. Elapsed: {}'.format(self.name,dtime))
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

        print('TCP Server OK')  

        while True:
            try:
                # set the timeout
                __socket.settimeout(2)
                # queue one request
                __socket.listen(1)    
                # establish a connection
                __clientsocket,addr = __socket.accept()   
                # print("TCP request from %s" % str(addr))

                if (addr[0][-3:] in self.allowed) or self.unlocked:
                    __clientsocket.send(self.data.encode('ascii'))
                    self.unallow(addr[0][-3:])

                __clientsocket.close()

                # make of set of connection IDs
                newId = str(addr[0]).split('.')[-1]
                self.newIds.add(newId)

            except socket.timeout:
                pass

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

    def allow(self, client_id):
        self.allowed.add(client_id)

    def unallow(self, client_id):
        self.allowed.discard(client_id)

    def getNew(self):
        if self.__stop:
            return set()
            print('Warning: TCP is OFF')

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
            print('TCP Server already ON')  

    def stop(self):
        """ This method is called before a clean exit """   
        self.__stop = 1
        print('TCP Server OFF') 



class Peer(object):
    """ Establish the Peer class 
    """
    def __init__(self, id__, enode = None, key=None, ageLimit = 0, w3 = None):
        """ Constructor
        :type id__: str
        :param id__: id of the peer
        """
        # Add the known peer details
        self.id = id__
        self.ip = '172.27.1.' + id__
        self.__tStamp = time.time()
        self.enode = enode
        self.key = key
        self.ageLimit = ageLimit
        self.w3 = w3
        self.isdead = 0
        self.age = 0
        

        # Initialize background daemon thread
        thread = threading.Thread(target=self.__aging, args=())
        thread.daemon = True   
        # Start the execution                         
        thread.start()   

    def __aging(self):
        """ This method runs in the background until program is closed 
        self.age is the time elapsed since the robots meeting.
        """            
        while True:
            self.age = time.time() - self.__tStamp

            if (self.enode != None) & (self.w3 != None):

                if not self.isPeer():
                    self.w3.geth.admin.addPeer(self.enode)

                if (self.ageLimit != 0) & (self.age > self.ageLimit):
                    self.kill()

            if self.isdead:
                break 
            else:
                time.sleep(0.1);   

    def reset_age(self):
        """ This method resets the timestamp of the robot meeting """ 
        self.__tStamp = time.time()
        # print('reseted peer age')

    def kill(self):
        """ This method kills the peer and ends the thread """
        self.isdead = 1
        cmd = "admin.removePeer(\"{}\")".format(self.enode)
        subprocess.call(["geth","--exec",cmd,"attach","/home/pi/mygethnode/geth.ipc"], stdout=subprocess.DEVNULL)   


    def isPeer(self):
        """ Checks if the peer is in geth list of peers """
        return self.enode in self.__gethEnodes()


    def __gethEnodes(self):
        try:
            return [peer.enode for peer in self.w3.geth.admin.peers()]
        except:
            print('didnt return gethEnodes for whatever reason')

