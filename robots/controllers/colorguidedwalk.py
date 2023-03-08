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

import sys

sys.path.append('/home/pi/apriltag/python')
import apriltag

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

robotID = open("/boot/pi-puck_id", "r").read().strip()
cam_int_reg_h = 100
cam_rot = True
cam_sample_lgh = 50
cam_sample_interval = 40
color_ce_threshold = 0.15  # cross entropy threshold, if a color is present
color_hsv_threshold = np.array([20, 60, 100])  # threshold for each dimension of the HSV
gsFreq = 20


def get_rgb_feature(image, length=20, interval=20):
    image_sz = image.shape
    feature = []
    idx = int(length / 2)
    while idx + int(length / 2) < image_sz[1]:
        hist_img = image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
        feature.append(hist_img / np.sum(hist_img))
        idx += interval
    return feature


def get_hsv_feature(image, length=20, interval=20):
    image_sz = image.shape
    feature = []
    idx = int(length / 2)
    while idx + int(length / 2) < image_sz[1]:
        hist_img = image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
        feature.append(hist_img[0])
        idx += interval
    return feature


def get_hsv_feature_center(image, length=30):
    # get averaged bgr feature of the center of current view, with bit larger interval
    image_sz = image.shape
    idx = int(image_sz[1] / 2)
    hist_img = image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
    return hist_img[0]


def get_rgb_feature_center(image, length=30):
    # get averaged bgr feature of the center of current view, with bit larger interval
    image_sz = image.shape
    idx = int(image_sz[1] / 2)
    hist_img = image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
    return hist_img / np.sum(hist_img)


def cross_entropy(dist_x, dist_y):
    loss = -np.sum(np.array(dist_x) * np.log(dist_y + 0.001))
    return loss / float(np.array(dist_y).shape[0])


def hue_distance(h0, h1):
    return min(abs(h1 - h0), 180 - abs(h1 - h0)) / 90.0


def angle_to_target(distance_to_target, color_threshold):
    middle_idx = len(distance_to_target) / 2
    all_idx = len(distance_to_target) / 2
    min_idx = np.argmin(distance_to_target)
    if min(distance_to_target) > color_threshold:
        return -10  # not found
    else:
        return (min_idx - middle_idx) / all_idx  # range -1 to +1


def get_contours(image_hsv, ground_truth_hsv, color_hsv_threshold):
    low_bound = np.minimum(np.maximum(np.array(ground_truth_hsv) - np.array(color_hsv_threshold), [0, 0, 0]),
                           [180, 255, 255])
    high_bound = np.minimum(np.maximum(np.array(ground_truth_hsv) + np.array(color_hsv_threshold), [0, 0, 0]),
                            [180, 255, 255])
    target_mask = cv2.inRange(image_hsv, low_bound, high_bound)
    # print(low_bound, high_bound)
    # cv2.imwrite('target_mask.jpg', target_mask)
    if ground_truth_hsv[0] + color_hsv_threshold[0] > 180:
        additional_threshold_up = ground_truth_hsv[0] + color_hsv_threshold[0] - 180
        add_bound = np.minimum(np.maximum(
            np.array([additional_threshold_up, ground_truth_hsv[1], ground_truth_hsv[2]]) - np.array(
                color_hsv_threshold), [0, 0, 0]),
                               [180, 255, 255])
        add_bound_low = np.minimum(np.maximum(
            np.array([0, ground_truth_hsv[1], ground_truth_hsv[2]]) - np.array(
                color_hsv_threshold), [0, 0, 0]),
            [180, 255, 255])
        add_target_mask = cv2.inRange(image_hsv, add_bound_low, add_bound)
        target_mask += add_target_mask
    elif ground_truth_hsv[0] - color_hsv_threshold[0] < 0:
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
    # cv2.imwrite('all_mask.jpg', target_mask)
    kernel = np.ones((5, 5), np.uint8)
    target_mask = cv2.erode(target_mask, kernel)
    kernel_d = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(target_mask, kernel_d)
    _, contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) != 0:
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        cX = int(M["m10"] / M["m00"])  # horizontal center of contour
        return c, cX
    else:
        return 0, -1


class ColorWalkEngine(object):
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
        self.gs = GroundSensor(gsFreq)
        self.gs.start()
        self.april = apriltag.Detector()
        if exists('calibration/' + robotID + '.csv'):
            with open('calibration/' + robotID + '.csv', 'r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.colors.append(elements[0])
                    self.ground_truth_bgr.append([int(x) for x in elements[1:]])
        else:
            print("color calibration fiule not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_bgr = [[0, 0, 255], [255, 0, 0], [226, 43, 138]]  # bgr
        if exists('calibration/' + robotID + '_hsv.csv'):
            with open('calibration/' + robotID + '_hsv.csv', 'r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.ground_truth_hsv.append([int(x) for x in elements[1:]])
        else:
            print("color calibration fiule not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_hsv = [[175, 255, 240], [100, 255, 172], [157, 157, 144]]  # bgr
        logger.info('Color walk OK')

    def discover_color(self, duration=10):
        startTime = time.time()
        while time.time() - startTime < duration:
            if self.rot.isWalking() == False:
                walk_dir = random.choice(["s", "cw", "ccw"])
                self.rot.setPattern(walk_dir, 5)
            else:
                color_idx, color_name, color_rgb = self.check_all_color()
                if color_idx != -1:
                    self.rot.setWalk(False)
                    return color_idx, color_name, color_rgb
        self.rot.setWalk(False)
        return -1, -1, -1

    def drive_to_hsv(self, this_color_hsv, duration=30):
        arrived_count = 0
        detect_color = False
        startTime = time.time()
        while arrived_count < 5 and time.time() - startTime < duration:
            newValues = self.gs.getAvg()
            if newValues:
                print(np.mean(newValues), newValues)
                if np.mean(newValues) > 700 and detect_color:  # see color and white board at once
                    self.rot.setWalk(False)
                    arrived_count += 1
                else:
                    arrived_count = 0
            image = self.cam.get_reading()
            image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            cnt, cen = get_contours(image_hsv, this_color_hsv, color_hsv_threshold)
            dir_ang = -1
            if cen != -1:
                detect_color = True
                dir_ang = (cen - 240) / 480
            else:
                detect_color = False
            print("angular direction: ", dir_ang)
            if abs(dir_ang) < 0.15:
                isTracking = True
            else:
                isTracking = False

            if isTracking:
                self.rot.setPattern("s", 5)
            elif dir_ang <= -1 and self.rot.isWalking() == False:
                # object not found, random walk
                walk_dir = random.choice(["s", "cw", "ccw"])
                self.rot.setPattern(walk_dir, 3)
            elif dir_ang > 0:
                print("cur angle: ", dir_ang)
                walk_time = np.ceil(1 + int(dir_ang))
                self.rot.setPattern("cw", walk_time)
            elif dir_ang < 0:
                print("cur angle: ", dir_ang)
                walk_time = np.ceil(1 - int(abs(dir_ang)))
                self.rot.setPattern("ccw", walk_time)
        self.rot.setWalk(False)
        if arrived_count == 5:
            return True
        else:
            return False

    def drive_to_color(self, color_name, duration=30):
        if color_name not in self.colors:
            print("unknown color")
            return False
        else:
            this_color_hsv = np.array(self.ground_truth_hsv[self.colors.index(color_name)])
            return self.drive_to_hsv(this_color_hsv, duration)

    def check_apriltag(self):
        image = self.cam.get_reading_raw()
        image_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        result = self.april.detect(image_grey)
        this_id = -1
        if result:
            this_id = result[0].tag_id
        else:
            print("Apriltag not found")
        return this_id

    def check_all_color(self):
        # for all hard coded colors
        max_contour = []
        max_color = ''
        max_color_idx = -1
        max_area = 1000 #minimum area threshold
        for color_idx, color_name in enumerate(self.colors):
            this_color_hsv = np.array(self.ground_truth_hsv[color_idx])
            image = self.cam.get_reading()
            image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            cnt, cen = get_contours(image_hsv, this_color_hsv, color_hsv_threshold)
            if cen != -1 and cv2.contourArea(cnt) > max_area:
                max_area = cv2.contourArea(cnt)
                max_color = color_name
                max_contour = cnt
                max_color_idx = color_idx
        if max_color_idx != -1:
            avg_color_mask = np.zeros(image.shape[:2], np.uint8)
            cv2.drawContours(avg_color_mask, [max_contour], -1, 255, -1)
            mean_color_rgb = cv2.mean(image, mask=avg_color_mask)
            print("max area: ", max_area, max_color)
            return max_color_idx, max_color, mean_color_rgb
        return -1, -1, -1

    def check_rgb_color(self, bgr_feature):
        # check specific bgr array
        this_color_hsv = cv2.cvtColor(np.array(bgr_feature, dtype=np.uint8).reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0][0]
        image = self.cam.get_reading()
        image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        cnt, cen = get_contours(image_hsv, this_color_hsv, color_hsv_threshold)
        if cen != -1:
            return 1
        else:
            return 0

    def drive_to_rgb(self, bgr_feature, duration=30):
        this_color_hsv = cv2.cvtColor(np.array(bgr_feature, dtype=np.uint8).reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0][0]
        return self.drive_to_hsv(this_color_hsv, duration)

    def get_color_list(self):
        return self.colors

    def set_leds(self, state):
        self.rot.setLEDs(state)


cwe = ColorWalkEngine(500)
print(cwe.discover_color(60)[1])
print(cwe.drive_to_color(cwe.discover_color(60)[1], duration=300))
tag_id = cwe.check_apriltag()
print(tag_id)
# while tag_id == -1:
#    tag_id = cwe.check_apriltag()
#    print(tag_id)
