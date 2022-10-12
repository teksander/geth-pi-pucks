#!/usr/bin/env python3
import random, math
import time
import smbus
import threading
import logging
from os.path import exists

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

robotID = open("/boot/pi-puck_id", "r").read().strip()

class WalktoColor(object):
    def __init__(self, MAX_SPEED):
        """ Constructor
        :type range: int
        :param enode:  (tip: 500)
        """
        self.colors = []
        self.ground_truth_bgr = []  # bgr
        if exists('calibration/'+robotID+'.csv'):
            with open('calibration/'+robotID+'.csv','r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.colors.append(elements[0])
                    self.ground_truth_bgr.append([int(x) for x in elements[1:]])
                    print(elements, self.colors, self.ground_truth_bgr)
        else:
            print("color calibration fiule not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_bgr = [[0, 0, 255], [255, 0, 0], [226, 43, 138]]  # bgr
        logger.info('Color walk OK')

wc = WalktoColor(300)