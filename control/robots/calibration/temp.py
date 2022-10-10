#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as np
import os
import time
import sys
#from matplotlib import pyplot as plt
sys.path.append('..')



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

image = cv2.imread("/home/ubuntu/test.jpg")
feature = get_rgb_feature()
distance_to_red = []
distance_to_blue = []
for local_feature in feature:
    distance_to_red.append((local_feature, cross_entropy(ground_truth_red, local_feature)))
    distance_to_blue.append((local_feature, cross_entropy(ground_truth_blue, local_feature)))
print("distance to red along y axis: ", distance_to_red)
print("distance to blue along y axis: ", distance_to_blue)