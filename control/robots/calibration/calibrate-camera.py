#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as np
import os
import time
import sys
#from matplotlib import pyplot as plt
sys.path.append('..')
from rotation import Rotation
from upcamera import UpCamera

cam_int_reg_h = 100
cam_rot = True
rotSpeed = 300
cam_sample_lgh = 20
cam_sample_interval = 20
max_samples = 1000


def cross_entropy(dist_x, dist_y):
    loss = -np.sum(np.array(dist_x)*np.log(dist_y))
    return loss/float(np.array(dist_y).shape[0])

cam = UpCamera(cam_int_reg_h, cam_rot)
rot = Rotation(rotSpeed)

image = cam.get_reading()
cv2.imwrite('test_capture.jpg', image)


ground_truth_red = [0,0,255] #b,g,r
ground_truth_green = [255,0,0]

while True:
    feature = cam.get_rgb_feature(cam_sample_lgh,cam_sample_interval)
    distance_to_red = []
    distance_to_green = []
    for local_feature in feature:
        distance_to_red.append(cross_entropy(ground_truth_red, local_feature))
        distance_to_green.append(cross_entropy(ground_truth_green, local_feature))
    print("distance to red along y axis: ", distance_to_red)
    print("distance to green along y axis: ", distance_to_green)



