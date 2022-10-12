#!/usr/bin/env python3
import random, math
import time
import smbus
import threading
import cv2
import numpy as np
import logging
from os.path import exists
from upcamera import UpCamera
from rotation import Rotation
from PID import PID

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

robotID = open("/boot/pi-puck_id", "r").read().strip()
cam_int_reg_h = 100
cam_rot = True
cam_sample_lgh = 20
cam_sample_interval = 20
color_ce_threshold =  0.2 #cross entropy threshold, if a color is present

def get_rgb_feature(image, length=20, interval=20):
    image_sz = image.shape
    feature = []
    idx = int(length / 2)
    while idx + int(length / 2) < image_sz[1]:
        hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
        feature.append(hist_img/np.sum(hist_img))
        idx += interval
    return feature
def get_rgb_feature_center(image, length=30):
    #get averaged bgr feature of the center of current view, with bit larger interval
    image_sz = image.shape
    idx = int(image_sz[1] / 2)
    hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
    return hist_img/np.sum(hist_img)

def cross_entropy(dist_x, dist_y):
    loss = -np.sum(np.array(dist_x)*np.log(dist_y))
    return loss/float(np.array(dist_y).shape[0])


class WalktoColor(object):
    def __init__(self, MAX_SPEED):
        """ Constructor
        :type range: int
        :param enode:  (tip: 500)
        """
        self.colors = []
        self.ground_truth_bgr = []  # bgr
        self.cam = UpCamera(cam_int_reg_h, cam_rot)

        if exists('calibration/'+robotID+'.csv'):
            with open('calibration/'+robotID+'.csv','r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.colors.append(elements[0])
                    self.ground_truth_bgr.append([int(x) for x in elements[1:]])
        else:
            print("color calibration fiule not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_bgr = [[0, 0, 255], [255, 0, 0], [226, 43, 138]]  # bgr
        logger.info('Color walk OK')

    def walktocolor(self,color_name):
        if color_name not in self.colors:
            print("unknown color")
            return 0
        else:
            this_color_feature = self.ground_truth_bgr[self.colors.index(color_name)]
            isTracking = False #color object is at center
            arrived = False
            while not arrived:
                image = self.cam.get_reading()
                center_rgb_feature = get_rgb_feature_center(image, length=40)
                if not isTracking:
                    cur_feature = get_rgb_feature(image, cam_sample_lgh,cam_sample_interval)




wc = WalktoColor(300)