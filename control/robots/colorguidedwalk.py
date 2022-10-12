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
    loss = -np.sum(np.array(dist_x)*np.log(dist_y+0.001))
    return loss/float(np.array(dist_y).shape[0])


def angle_to_target(distance_to_target, color_threshold):
    middle_idx = len(distance_to_target)/2
    all_idx = len(distance_to_target) / 2
    min_idx = np.argmin(distance_to_target)
    if min_idx > color_threshold:
        return -10 #not found
    else:
        return (min_idx-middle_idx)/all_idx #range -1 to +1

class WalktoColor(object):
    def __init__(self, MAX_SPEED):
        """ Constructor
        :type range: int
        :param enode:  (tip: 500)
        """
        self.colors = []
        self.ground_truth_bgr = []  # bgr
        self.cam = UpCamera(cam_int_reg_h, cam_rot)
        self.rot = Rotation(MAX_SPEED)
        self.rot.start("s")
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

    def start(self,color_name):
        if color_name not in self.colors:
            print("unknown color")
            return 0
        else:
            this_color_feature = np.array(self.ground_truth_bgr[self.colors.index(color_name)])/np.sum(self.ground_truth_bgr[self.colors.index(color_name)])
            isTracking = False #color object is at center
            arrived = False
            while not arrived:
                image = self.cam.get_reading()
                center_rgb_feature = get_rgb_feature_center(image, length=5)
                if cross_entropy(this_color_feature, center_rgb_feature)<color_ce_threshold:
                    print("center distance: ", cross_entropy(this_color_feature, center_rgb_feature))
                    isTracking = True
                    self.rot.setPattern("s", 5)
                else:
                    print("center distance: ", cross_entropy(this_color_feature, center_rgb_feature))
                    isTracking = False
                if not isTracking:
                    cur_feature = get_rgb_feature(image, cam_sample_lgh,cam_sample_interval)
                    distance_to_target = []
                    for local_feature in cur_feature:
                        distance_to_target.append(cross_entropy(this_color_feature, local_feature))
                    print(distance_to_target)
                    dir = angle_to_target(distance_to_target, color_ce_threshold)
                    print("angular direction: ", dir)
                    if dir <= -1:
                        #object not found, random walk
                        walk_dir = random.choice(["s", "cw", "ccw"])
                        self.rot.setPattern(walk_dir, 5)
                    elif dir > 0:
                        print("cur angle: ", dir)
                        walk_time = np.ceil(3+dir*10)
                        self.rot.setPattern("cw", walk_time)
                    elif dir < 0:
                        print("cur angle: ", dir)
                        walk_time = np.ceil(3-(dir*10))
                        self.rot.setPattern("ccw", walk_time)


wc = WalktoColor(500)
wc.start("red")