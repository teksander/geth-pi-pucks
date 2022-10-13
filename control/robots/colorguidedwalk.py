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
from groundsensor import GroundSensor
from PID import PID

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

robotID = open("/boot/pi-puck_id", "r").read().strip()
cam_int_reg_h = 100
cam_rot = True
cam_sample_lgh = 50
cam_sample_interval = 40
color_ce_threshold =  0.15 #cross entropy threshold, if a color is present
color_hsv_threshold = np.array([20, 60, 100]) #threshold for each dimension of the HSV
gsFreq=20
def get_rgb_feature(image, length=20, interval=20):
    image_sz = image.shape
    feature = []
    idx = int(length / 2)
    while idx + int(length / 2) < image_sz[1]:
        hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
        feature.append(hist_img/np.sum(hist_img))
        idx += interval
    return feature

def get_hsv_feature(image, length=20, interval=20):
    image_sz = image.shape
    feature = []
    idx = int(length / 2)
    while idx + int(length / 2) < image_sz[1]:
        hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
        feature.append(hist_img[0])
        idx += interval
    return feature
def get_hsv_feature_center(image, length=30):
    #get averaged bgr feature of the center of current view, with bit larger interval
    image_sz = image.shape
    idx = int(image_sz[1] / 2)
    hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
    return hist_img[0]

def get_rgb_feature_center(image, length=30):
    #get averaged bgr feature of the center of current view, with bit larger interval
    image_sz = image.shape
    idx = int(image_sz[1] / 2)
    hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
    return hist_img/np.sum(hist_img)

def cross_entropy(dist_x, dist_y):
    loss = -np.sum(np.array(dist_x)*np.log(dist_y+0.001))
    return loss/float(np.array(dist_y).shape[0])

def hue_distance(h0,h1):
    return min(abs(h1-h0), 180-abs(h1-h0)) / 90.0

def angle_to_target(distance_to_target, color_threshold):
    middle_idx = len(distance_to_target)/2
    all_idx = len(distance_to_target) / 2
    min_idx = np.argmin(distance_to_target)
    if min(distance_to_target) > color_threshold:
        return -10 #not found
    else:
        return (min_idx-middle_idx)/all_idx #range -1 to +1

def get_contours(image_hsv, ground_truth_hsv, color_hsv_threshold):
    low_bound = np.minimum(np.maximum(np.array(ground_truth_hsv)-np.array(color_hsv_threshold),[0,0,0]), [180,255, 255])
    high_bound = np.minimum(np.maximum(np.array(ground_truth_hsv)+np.array(color_hsv_threshold),[0,0,0]), [180,255, 255])
    target_mask = cv2.inRange(image_hsv, low_bound, high_bound)
    #print(low_bound, high_bound)
    #cv2.imwrite('target_mask.jpg', target_mask)
    if ground_truth_hsv[0] + color_hsv_threshold[0] > 180:
        additional_threshold_up = ground_truth_hsv[0] + color_hsv_threshold[0] - 180
        add_bound = np.minimum(np.maximum(np.array([additional_threshold_up, ground_truth_hsv[1],ground_truth_hsv[2]]) - np.array(color_hsv_threshold), [0, 0, 0]),
                               [180, 255, 255])
        add_bound_low = np.minimum(np.maximum(
            np.array([0, ground_truth_hsv[1], ground_truth_hsv[2]]) - np.array(
                color_hsv_threshold), [0, 0, 0]),
                               [180, 255, 255])
        add_target_mask = cv2.inRange(image_hsv, add_bound_low, add_bound)
        target_mask += add_target_mask
    elif ground_truth_hsv[0] - color_hsv_threshold[0] <0:
        additional_threshold_low = 180 + ground_truth_hsv[0] - color_hsv_threshold[0]
        add_bound = np.minimum(np.maximum(
            np.array([additional_threshold_low, ground_truth_hsv[1], ground_truth_hsv[2]]) - np.array(
                color_hsv_threshold), [0, 0, 0]),
                               [180, 255, 255])
        add_bound_high = np.minimum(np.maximum(
            np.array([180, ground_truth_hsv[1], ground_truth_hsv[2]]) + np.array(
                color_hsv_threshold), [0, 0, 0]),
            [180, 255, 255])
        add_target_mask = cv2.inRange(image_hsv, add_bound, add_bound_high)
        target_mask += add_target_mask
    #cv2.imwrite('all_mask.jpg', target_mask)
    kernel = np.ones((5,5), np.uint8)
    target_mask = cv2.erode(target_mask, kernel)
    kernel_d = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(target_mask, kernel_d)
    _, contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours)!=0:
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        cX = int(M["m10"] / M["m00"]) #horizontal center of contour
        return c, cX
    else:
        return 0, -1


class WalktoColor(object):
    def __init__(self, MAX_SPEED):
        """ Constructor
        :type range: int
        :param enode:  (tip: 500)
        """
        self.colors = []
        self.ground_truth_bgr = []  # bgr
        self.ground_truth_hsv = []  # bgr
        self.cam = UpCamera(cam_int_reg_h, cam_rot)
        self.rot = Rotation(MAX_SPEED)
        self.rot.start()
        self.gs=GroundSensor(gsFreq)
        self.gs.start()
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
        if exists('calibration/'+robotID+'_hsv.csv'):
            with open('calibration/'+robotID+'_hsv.csv','r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.ground_truth_hsv.append([int(x) for x in elements[1:]])
        else:
            print("color calibration fiule not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_hsv = [[175, 255, 240], [100, 255, 172], [157, 157, 144]]  # bgr
        logger.info('Color walk OK')

    def start(self,color_name):
        if color_name not in self.colors:
            print("unknown color")
            return 0
        else:
            this_color_hsv = np.array(self.ground_truth_hsv[self.colors.index(color_name)])
            isTracking = False #color object is at center
            arrived = False
            while not arrived:
                newValues = self.gs.getAvg()
                if newValues:
                    print(np.mean(newValues), newValues)
                    if np.mean(newValues) > 700:
                        arrived = True
                        self.rot.setWalk(False)
                    else:
                        arrived = False
                image = self.cam.get_reading()
                image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                cnt, cen = get_contours(image_hsv, this_color_hsv, color_hsv_threshold)
                dir_ang=-1
                if cen!=-1:
                    dir_ang=(cen-240)/480
                print("angular direction: ", dir_ang)
                if abs(dir_ang) < 0.2:
                    isTracking = True
                else:
                    isTracking = False

                if isTracking:
                    self.rot.setPattern("s", 5)
                elif dir_ang <= -1:
                    #object not found, random walk
                    walk_dir = random.choice(["s", "cw", "ccw"])
                    #self.rot.setPattern(walk_dir, 5)
                elif dir_ang > 0:
                    print("cur angle: ", dir_ang)
                    walk_time = np.ceil(1+int(dir_ang))
                    self.rot.setPattern("cw", walk_time)
                elif dir_ang < 0:
                    print("cur angle: ", dir_ang)
                    walk_time = np.ceil(1-int(abs(dir_ang)))
                    self.rot.setPattern("ccw", walk_time)



wc = WalktoColor(500)
wc.start("purple")