#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as np
import os
import time
import sys
import time
#from matplotlib import pyplot as plt
sys.path.append('..')
sys.path.append('../controllers')
from rotation import Rotation
from upcamera import UpCamera

cam_int_reg_h = 200
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
    cropped_image_tmp = image[:, idx - int(length / 2):idx + int(length / 2)].copy()
    return hist_img, cropped_image_tmp
def get_hsv_center(image, length=30):
    image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    image_sz = image_hsv.shape
    idx = int(image_sz[1] / 2)
    hist_img= image_hsv[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0).mean(axis=0).astype(int)
    return hist_img

def set_color():
    image = cam.get_reading()
    image_r = cam.get_reading_raw()
    cv2.imwrite(robotID + '_raw_reading_test.jpg', image_r)
    readings = []
    for idx in range(10):
        image = cam.get_reading()
        mean_rgb, _ = get_rgb_center(image, 60)
        readings.append(mean_rgb)
    print("color ground truth bgr set to: ", np.mean(readings, axis=0).astype(int))
    _, cropped_image = get_rgb_center(image, 60)
    return np.mean(readings, axis=0).astype(int), cropped_image


def set_color_hsv():
    cam.get_reading()
    readings = []
    for idx in range(10):
        image = cam.get_reading()
        readings.append(get_hsv_center(image,60))
    print("color ground truth hsv set to: ", np.mean(readings,axis=0).astype(int))
    return np.mean(readings,axis=0).astype(int)


def single_time_test():
    while True:
        print("Present a color")
        input("Press Enter to continue...")
        ground_truth_bgr, cropped_image = set_color()
        ground_truth_hsv = set_color_hsv()
        print("got reading, bgr: ", ground_truth_bgr, " hsv: ", ground_truth_hsv)
        cv2.imwrite(robotID + '_one_time_test.jpg', cropped_image)


if __name__ == "__main__":
    cam = UpCamera(200, 50)
    image = cam.get_reading_raw()

    height1, width1 = image.shape[:2]


    colors = ["red", "blue", "purple", "green"]
    ground_truth_bgr = [[0,0,255], [255,0,0], [226, 43, 138],[0,255,0]] #bgr
    ground_truth_hsv = [[0,0,0], [0,0,0], [0,0,0], [0,0,0]] #hsv

    if ask_yesno("calibrate color ground truth?"):
        for idx, name in enumerate(colors):
            print("Present " + name +" color")
            input("Press Enter to continue...")
            ground_truth_bgr[idx], cropped_image = set_color()
            ground_truth_hsv[idx] = set_color_hsv()
            h2, w2 = cropped_image.shape[:2]
            cropped_image = cv2.resize(cropped_image, (w2, height1))
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
    #single_time_test()






