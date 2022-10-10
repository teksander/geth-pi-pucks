#!/usr/bin/env python3

import cv2 #sudo apt-get install python-opencv
import numpy as py
import os
import time
import sys
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