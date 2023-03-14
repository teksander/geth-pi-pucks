#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as np
import os
import time
import sys
#from matplotlib import pyplot as plt
sys.path.append('..')
sys.path.append('../controllers')
from rotation import Rotation
from upcamera import UpCamera

cam_int_reg_h = 100
cam_rot = True
rotSpeed = 300
cam_sample_lgh = 20
cam_sample_interval = 20
max_samples = 1000
robotID = open("/boot/pi-puck_id", "r").read().strip()

def cross_entropy(dist_x, dist_y):
    loss = -np.sum(np.array(dist_x)*np.log(dist_y))
    return loss/float(np.array(dist_y).shape[0])


def ask_yesno(question):
    """
    Helper to get yes / no answer from user.
    """
    yes = {'yes', 'y'}
    no = {'no', 'n'}  # pylint: disable=invalid-name

    done = False
    print(question)
    while not done:
        choice = input().lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            print("Please respond by yes or no.")


def get_rgb_center(image, length=30):
    image_sz = image.shape
    idx = int(image_sz[1] / 2)
    hist_img= image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0).astype(int)
    cropped_image = image[:, idx - int(length / 2):idx + int(length / 2)]
    return hist_img, cropped_image
def get_hsv_center(image, length=30):
    image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    image_sz = image_hsv.shape
    idx = int(image_sz[1] / 2)
    hist_img= image_hsv[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0).astype(int)
    return hist_img

def set_color():
    image = cam.get_reading()
    mean_rgb, cropped_image = get_rgb_center(image, 30)
    print("color ground truth  set to: ", mean_rgb)
    return mean_rgb, cropped_image

def set_color_hsv():
    image = cam.get_reading()
    print("color ground truth hsv set to: ", get_hsv_center(image,30))
    return get_hsv_center(image,30)
cam = UpCamera(cam_int_reg_h, cam_rot)

image = cam.get_reading()

height1, width1 = image.shape[:2]


colors = ["red", "blue", "purple"]
ground_truth_bgr = [[0,0,255], [255,0,0], [226, 43, 138]] #bgr
ground_truth_hsv = [[0,0,0], [0,0,0], [0,0,0]] #hsv

if ask_yesno("calibrate color ground truth?"):
    for idx, name in enumerate(colors):
        print("Present " + name +" color")
        input("Press Enter to continue...")
        ground_truth_bgr[idx], cropped_image = set_color()
        ground_truth_hsv[idx] = set_color_hsv()
        h2, w2 = cropped_image.shape[:2]
        cropped_image = cv2.resize(cropped_image, (w2, height1))
        print(image.shape, cropped_image.shape)
        image = cv2.hconcat([image, cropped_image])

cv2.imwrite(robotID+'_test_capture.jpg', image)
#write color ground truth result
color_gt = open(robotID+'.csv','w+')
color_hsv_gt = open(robotID+'_hsv.csv','w+')
for idx, name in enumerate(colors):
    color_gt.write(name+' '+' '.join([str(x) for x in ground_truth_bgr[idx]])+'\n')
    color_hsv_gt.write(name + ' ' + ' '.join([str(x) for x in ground_truth_hsv[idx]]) + '\n')
color_gt.close()
color_hsv_gt.close()






