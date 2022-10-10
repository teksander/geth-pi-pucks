import cv2 #sudo apt-get install python-opencv
import numpy as py
import os
import time
from rotation import Rotation
from upcamera import UpCamera

cam_int_reg_h = 100
cam_rot = True
rotSpeed = 300

cam = UpCamera(cam_int_reg_h, cam_rot)
rot = Rotation(rotSpeed)

