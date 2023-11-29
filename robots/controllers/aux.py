#!/usr/bin/env python3
import time
import math
import threading
import socket
import os
import logging
import json
import subprocess

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

class Timer:
    def __init__(self, rate, name = None):
        self.name = name
        self.rate = rate
        self.time = time.time()
        self.isLocked = False

    def query(self, reset = True):
        if self.remaining() < 0:
            if reset:
                self.reset()
            return True
        else:
            return False

    def remaining(self):
        return self.rate - (time.time() - self.time)

    def set(self, rate):
        if not self.isLocked:
            self.rate = rate
            self.time = time.time()
        return self

    def reset(self):
        if not self.isLocked:
            self.time = time.time()
        return self

    def lock(self):
        self.isLocked = True
        return self

    def unlock(self):
        self.isLocked = False
        return self



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

    def allow(self, client_id):
        self.allowed.add(client_id)

    def unallow(self, client_id):
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

    def setTimeout(self, timeout = 4):
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

    def __aging(self):
        """ This method runs in the background until program is closed 
        self.age is the time elapsed since the robots meeting.
        """            
        while True:

            self.step()

            if self.__stop:
                break
            else:
                time.sleep(0.05);   

    def step(self):
        """ This method performs a single sequence of operations """          

        for peer in self.buffer:
            peer.age = time.time() - peer.tStamp

            if peer.age > self.ageLimit:
                peer.kill()

            if peer.timeout != 0:
                if (peer.timeout - (time.time() - peer.timeoutStamp)) <= 0:
                    peer.timeout = 0      


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



class Logger(object):
    """ Logging Class to Record Data to a File
    """
    def __init__(self, logfile, header, rate = 0, buffering = 1, ID = None, extrafields = {}):

        self.file = open(logfile, 'w+', buffering = buffering)
        self.rate = rate
        self.tStamp = 0
        self.tStart = 0
        self.latest = time.time()
        self.extra  = extrafields.values()
        pHeader = ' '.join([str(x) for x in header]+[str(x) for x in extrafields])
        self.file.write('{} {} {}\n'.format('ID', 'TIME', pHeader))
        
        if ID:
            self.id = ID
        else:
            self.id = open("/boot/pi-puck_id", "r").read().strip()

    def log(self, data):
        """ Method to log row of data
        :param data: row of data to log
        :type data: list
        """ 
        
        if self.query():
            self.tStamp = time.time()
            try:
                tString = str(round(self.tStamp-self.tStart, 3))
                pData = ' '.join([str(x) for x in data]+[str(x) for x in self.extra])
                self.file.write('{} {} {}\n'.format(self.id, tString, pData))
                self.latest = self.tStamp
            except:
                pass
                logger.warning('Failed to log data to file')

    def query(self):
        return time.time()-self.tStamp > self.rate

    def start(self):
        self.tStart = time.time()

    def close(self):
        self.file.close()


def list2dict(values, keys):
    
    if not values:
        return {}

    if len(values) != len(keys):
        raise ValueError("Values and keys should be equal length")

    return {k: values[i] for i, k in enumerate(keys)}

def rgb_to_ansi(rgb):
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m"

def print_color(*variables, color_rgb):
    # Convert variables to strings
    strings = [str(var) for var in variables]
    
    # Generate the ANSI escape sequence for the specified RGB color
    color_code = f"\033[38;2;{color_rgb[0]};{color_rgb[1]};{color_rgb[2]}m"
    
    # Concatenate the strings and print them with the specified color
    print(color_code + " ".join(strings) + "\033[0m")


def print_dict(d, indent=0):
    for key, value in d.items():
        print('\t' * indent + str(key) + ': ', end='')
        if isinstance(value, dict):
            print('')
            print_dict(value, indent+1)
        else:
            print(str(value))

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

def colourBGRDistance(p1, p2):
    space_size = len(p1)
    divisor = 100000
    rp1 = [0] * space_size
    rp2 = [0] * space_size

    for i in range(space_size):
        rounded = p1[i] // divisor

        if rounded < 0:
            rounded = 0
        rp1[i] = rounded

        rounded = p2[i] // divisor
        if rounded < 0:
            rounded = 0
        rp2[i] = rounded

    rMean = (rp1[2] + rp2[2]) // 2
    r = rp1[2] - rp2[2]
    g = rp1[1] - rp2[1]
    b = rp1[0] - rp2[0]
    distance = ((((512 + rMean) * r * r) >> 8) + 4 * g * g + (((767 - rMean) * b * b) >> 8))
    distance = math.sqrt(distance) * 100000
    return distance

def manhattan_distance(p1, p2):
    """
    Compute the Manhattan distance between two points.
    
    Arguments:
    p1, p2 -- Tuples or lists representing the coordinates of the two points.
    
    Returns:
    The Manhattan distance between the two points.
    """
    if len(p1) != len(p2):
        raise ValueError("Both points should have the same number of coordinates.")
    
    distance = 0
    for i in range(len(p1)):
        distance += abs(p1[i] - p2[i])
    
    return distance

def chebyshev_distance(point1, point2):
    """
    Compute the Chebyshev distance between two points.
    
    Arguments:
    point1, point2 -- Tuples or lists representing the coordinates of the two points.
    
    Returns:
    The Chebyshev distance between the two points.
    """
    if len(point1) != len(point2):
        raise ValueError("Both points should have the same number of coordinates.")
    
    distance = 0
    for i in range(len(point1)):
        distance = max(distance, abs(point1[i] - point2[i]))
    
    return distance

def readEnode(enode, output = 'id'):
    # Read IP or ID from an enode
    ip_ = enode.split('@',2)[1].split(':',2)[0]

    if output == 'ip':
        return ip_
    elif output == 'id':
        return ip_.split('.')[-1] 

def getCPUPercent():
    try:
        cpu_usage = str(round(float(os.popen('''grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage }' ''').readline()),2))
    except:
        cpu_usage = 0
    return cpu_usage

def get_process_stats(process_name):
    pgrep_command = subprocess.Popen(['pgrep', '-f', process_name], stdout=subprocess.PIPE)
    pid_list, _ = pgrep_command.communicate()
    pids = pid_list.decode().split()

    if pids:
        pid = pids[0]
        ps_command = subprocess.Popen(['ps', '-p', pid, '-o', '%cpu,%mem'], stdout=subprocess.PIPE)
        output, _ = ps_command.communicate()
        process_stats = output.decode().split('\n')[1].split()
        cpu_percent = float(process_stats[0])
        mem_percent = float(process_stats[1])
        return cpu_percent, mem_percent
    else:
        return None, None
    
def get_folder_size(folder):
    # Return the size of a folder
    total_size = os.path.getsize(folder)
    for item in os.listdir(folder):
        itempath = os.path.join(folder, item)
        if os.path.isfile(itempath):
            total_size += os.path.getsize(itempath)
        elif os.path.isdir(itempath):
            total_size += get_folder_size(itempath)
    return total_size

def mapping_id_keys(directory_path, limit=None):
    id_to_key = {}
    key_to_id = {}
    count = 0

    for i in range(limit):
        folder_name = str(i)
        file_path = os.path.join(directory_path, folder_name, folder_name)

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                key = "0x"+data["address"]
                id_to_key[folder_name] = key
                key_to_id[key] = folder_name
                count += 1
                if count == limit:
                    break

    return id_to_key, key_to_id

import random
def simulate_camera_defect(color, defect_type=None, intensity=0.2):
    """
    Simulates camera defects by adding biased noise to an RGB color.

    Args:
        color (list): The original RGB color as a list [R, G, B].
        defect_type (str): The type of camera defect. Options: 'red_blindness', 'green_blindness', 'blue_blindness', 'shade_effect'.
        intensity (float): The intensity of the defect, ranging from 0 to 1. Higher values result in more severe defects.

    Returns:
        list: The modified RGB color with added camera defect.
    """
    r, g, b = color

    if defect_type in ['red_blindness', 'green_blindness', 'blue_blindness']:
        if defect_type == 'red_blindness':
            r = r * (1 - intensity) + random.uniform(0, intensity * r)
        elif defect_type == 'green_blindness':
            g = g * (1 - intensity) + random.uniform(0, intensity * g)
        elif defect_type == 'blue_blindness':
            b = b * (1 - intensity) + random.uniform(0, intensity * b)

    if defect_type == 'shade_effect':
        r = r * (1 - intensity) + random.uniform(0, intensity * 255)
        g = g * (1 - intensity) + random.uniform(0, intensity * 255)
        b = b * (1 - intensity) + random.uniform(0, intensity * 255)

    return [int(r), int(g), int(b)]

import cv2
import numpy as np
def bgr_to_hsv(bgr_color):
    """
    Converts a BGR color to HSV color space using OpenCV.

    Args:
        bgr_color (list): The BGR color as a list [B, G, R].

    Returns:
        list: The corresponding HSV color as a list [H, S, V].
    """
    return cv2.cvtColor(np.array(bgr_color, dtype=np.uint8).reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0][0]