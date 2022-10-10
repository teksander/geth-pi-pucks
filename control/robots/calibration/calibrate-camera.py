#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as py
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
max_samples = 1000


cam = UpCamera(cam_int_reg_h, cam_rot)
rot = Rotation(rotSpeed)

image = cam.get_reading()
cv2.imwrite('test_capture.jpg', image)
'''
def rgb_hist(image):
    colors = ('b', 'g', 'r')
    for i, col in enumerate(colors):
        histr = cv2.calcHist([image],[i],None,[256],[0,256])
        plt.plot(histr, color= col )
        plt.xlim([0,256])
    plt.show()

rgb_hist(image)
'''