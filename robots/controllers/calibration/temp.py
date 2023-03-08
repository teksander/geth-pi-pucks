#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as np
import os
import time
import sys
import matplotlib.pyplot as plt
#from matplotlib import pyplot as plt
sys.path.append('..')

from boxdetect import config


cfg = config.PipelinesConfig()

# important to adjust these values to match the size of boxes on your image
cfg.width_range = (30,480)
cfg.height_range = (30,640)

# the more scaling factors the more accurate the results but also it takes more time to processing
# too small scaling factor may cause false positives
# too big scaling factor will take a lot of processing time
cfg.scaling_factors = [0.3]

# w/h ratio range for boxes/rectangles filtering
cfg.wh_ratio_range = (0.5, 1.7)

# group_size_range starting from 2 will skip all the groups
# with a single box detected inside (like checkboxes)
cfg.group_size_range = (2, 100)

# num of iterations when running dilation tranformation (to engance the image)
cfg.dilation_iterations = 0


def cross_entropy(dist_x, dist_y):
    loss = -np.sum(np.array(dist_x)*np.log(dist_y))
    return loss/float(np.array(dist_y).shape[0])


def crossEntropy(Y, P):
    Y = np.float_(Y)
    P = np.float_(P)
    CE = -np.sum(Y*np.log(P) + (1-Y)*np.log(1-P))
    return CE

ground_truth_red = [0, 0, 1] #b,g,r
ground_truth_blue = [1,0,0]


def get_rgb_feature(length=20, interval=20):
    image = cv2.imread("/home/ubuntu/test.jpg")
    image_sz = image.shape
    feature = []
    idx = int(length / 2)
    while idx + int(length / 2) < image_sz[1]:
        hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0)
        feature.append(hist_img/np.sum(hist_img))
        idx += interval
    return feature


def get_contours(image_hsv, ground_truth_hsv, color_hsv_threshold):
    low_bound = np.minimum(np.maximum(np.array(ground_truth_hsv)-np.array(color_hsv_threshold),[0,0,0]), [180,255, 255])
    high_bound = np.minimum(np.maximum(np.array(ground_truth_hsv)+np.array(color_hsv_threshold),[0,0,0]), [180,255, 255])
    target_mask = cv2.inRange(image_hsv, low_bound, high_bound)
    kernel = np.ones((6,6), np.uint8)
    target_mask = cv2.erode(target_mask, kernel)
    kernel_d = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(target_mask, kernel_d)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours)!=0:
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        cX = int(M["m10"] / M["m00"]) #horizontal center of contour
        return c, cX
    else:
        return 0, 0

file_name = "/home/ubuntu/test.jpg"
image = cv2.imread("/home/ubuntu/test.jpg")
image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
this_ground_truth_hsv = [175, 255, 240]
color_hsv_threshold = np.array([20, 60, 100])
cnt, cen = get_contours(image_hsv, this_ground_truth_hsv, color_hsv_threshold)
cv2.drawContours(image, [cnt], 0, (0, 0, 0), 5)
plt.imshow(image)
plt.show()