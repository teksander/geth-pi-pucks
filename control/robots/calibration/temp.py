#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as np
import os
import time
import sys
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


from boxdetect.pipelines import get_boxes
file_name = "/home/ubuntu/test.jpg"
rects, grouping_rects, image, output_image = get_boxes(
    file_name, cfg=cfg, plot=False)