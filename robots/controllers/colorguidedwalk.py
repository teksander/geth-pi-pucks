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
sys.path.append('/home/pi/geth-pi-pucks/robots/arducam/apriltag/python')
import apriltag

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)

robotID = open("/boot/pi-puck_id", "r").read().strip()
cam_int_reg_h = 200
cam_int_reg_offest = 50
cam_rot = True
cam_sample_lgh = 50
cam_sample_interval = 40
color_ce_threshold = 0.15  # cross entropy threshold, if a color is present
color_hsv_threshold = np.array([12, 70, 100])  # threshold for each dimension of the HSV
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


#PID controller for drive to color
class PID:
    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.previous_error = 0
        self.integral = 0

    def compute(self, error, dt):
        self.integral += error * dt
        derivative = (error - self.previous_error) / dt
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        self.previous_error = error
        return output


class ColorWalkEngine(object):
    def __init__(self, MAX_SPEED):
        """ Constructor
        :type range: int
        :param enode:  (tip: 500)
        """
        self.colors = []
        self.ground_truth_bgr = []  # bgr
        self.ground_truth_hsv = []  # bgr
        self.cam = UpCamera(cam_int_reg_h, cam_int_reg_offest, cam_rot)
        self.rot = Rotation(MAX_SPEED)
        self.rot.start()
        #self.gs = GroundSensor(gsFreq)
        #self.gs.start()
        self.april = apriltag.Detector()
        self.max_speed= MAX_SPEED
        self.actual_rw_dir = "s"
        self.last_speed = []
        if exists('../calibration/' + robotID + '.csv'):
            with open('../calibration/' + robotID + '.csv', 'r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.colors.append(elements[0])
                    self.ground_truth_bgr.append([int(x) for x in elements[1:]])
        else:
            print("color calibration file not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_bgr = [[0, 0, 255], [255, 0, 0], [226, 43, 138]]  # bgr
        if exists('../calibration/' + robotID + '_hsv.csv'):
            with open('../calibration/' + robotID + '_hsv.csv', 'r') as color_gt:
                for line in color_gt:
                    elements = line.strip().split(' ')
                    self.ground_truth_hsv.append([int(x) for x in elements[1:]])
        else:
            print("color calibration fiule not found, use hard coded colors")
            self.colors = ["red", "blue", "purple"]
            self.ground_truth_hsv = [[175, 255, 240], [100, 255, 172], [157, 157, 144]]  # bgr
        logger.info('Color walk OK')

    def random_walk_engine(self, mylambda= 15, turn = 7):
        self.rot.setDrivingMode("pattern")
        if self.rot.duration <= 0:
            if self.actual_rw_dir == "s":
                self.actual_rw_dir = random.choice(["s", "cw", "ccw"])
                time_to_walk = math.ceil(random.uniform(0, 1) * turn)
            else:
                time_to_walk = math.ceil(random.expovariate(1 / mylambda))
                self.actual_rw_dir = "s"
            #print("drivign pattern set to: ", self.actual_rw_dir, time_to_walk)
            self.rot.setPattern(self.actual_rw_dir, time_to_walk)

    def discover_color(self, duration=10):
        startTime = time.time()
        #self.random_walk_engine() #walk a bit first
        self.actual_rw_dir = "s"
        while time.time() - startTime < duration:
            if self.rot.duration <= 0:
                color_idx, color_name, color_rgb,_ = self.check_all_color()
                if color_idx != -1 and self.check_free_zone():
                    self.rot.setWalk(False)
                    return color_idx, color_name, color_rgb
                self.random_walk_engine()

        self.rot.setWalk(False)
        return -1, -1, -1

    def repeat_sampling(self, color_name, repeat_times = 5):
        measure_list = []
        for idx in range(repeat_times):
            found_color_idx, found_color_name, found_color_rgb, found_color_center = self.check_all_color()
            if color_name == found_color_name:
                measure_list.append(found_color_rgb)
            if (480 // 2 - found_color_center)>0: #if target on your right
                walk_dir = ["cw", "ccw"][idx % 2]
            else:
                walk_dir = ["ccw", "cw"][idx % 2]
            self.rot.setPattern(walk_dir, 1)
        if measure_list:
            return np.mean(measure_list,axis=0)
        else:
            return [-1,-1,-1]
   

    def check_apriltag(self):
        image = self.cam.get_reading_raw()
        image_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        result = self.april.detect(image_grey)
        maximum_h = 0
        this_id = 0

        if result:
            for this_tag in result:
                this_h = max(abs(this_tag.corners[0][1]- this_tag.corners[1][1]), abs(this_tag.corners[2][1]- this_tag.corners[3][1]))
                if this_h>maximum_h:
                    maximum_h = this_h
                    this_id = this_tag.tag_id
        return this_id, maximum_h

    def check_all_color(self, max_area = 5000):
        # for all hard coded colors
        max_contour = []
        max_color = ''
        max_color_idx = -1
        this_area = max_area
        cen = -1
        image = self.cam.get_reading()
        for color_idx, color_name in enumerate(self.colors):
            this_color_hsv = np.array(self.ground_truth_hsv[color_idx])
            image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            cnt, cen = get_contours(image_hsv, this_color_hsv, color_hsv_threshold)
            if cen != -1:
                print(color_idx,color_name, cv2.contourArea(cnt))
            if cen != -1 and cv2.contourArea(cnt) > this_area:
                this_area = cv2.contourArea(cnt)
                max_color = color_name
                max_contour = cnt
                max_color_idx = color_idx
        if max_color_idx != -1:
            avg_color_mask = np.zeros(image.shape[:2], np.uint8)
            cv2.drawContours(avg_color_mask, [max_contour], -1, 255, -1)
            mean_color_rgb = cv2.mean(image, mask=avg_color_mask)[:3]
            print("max area: ", int(this_area), max_color, [int(a) for a in mean_color_rgb])
            return max_color_idx, max_color, mean_color_rgb, cen
        return -1, -1, [-1,-1,-1], -1

    def check_free_zone(self):
        _, tag_height = self.check_apriltag()
        if tag_height>0:
            if tag_height < 100:
                return True #in free ground
            else:
                return False
        else:
            return True
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

    def drive_to_closest_color(self, bgr_feature, duration=30):
        this_color_hsv = cv2.cvtColor(np.array(bgr_feature, dtype=np.uint8).reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0][0]
        closest_color = self.colors[0]
        closest_color_idx = 0
        closest_color_dist = hue_distance(self.ground_truth_hsv[0][0], this_color_hsv[0])
        for idx, this_color in enumerate(self.colors):
            if hue_distance(self.ground_truth_hsv[idx][0], this_color_hsv[0]) < closest_color_dist:
                closest_color_dist = hue_distance(self.ground_truth_hsv[idx][0], this_color_hsv[0])
                closest_color = this_color
                closest_color_idx = idx
        isArrived = self.drive_to_color(closest_color, duration)
        return isArrived, closest_color, closest_color_idx

    def drive_to_closest_color_byz(self, bgr_feature, confusing_set, duration=30):
        this_color_hsv = cv2.cvtColor(np.array(bgr_feature, dtype=np.uint8).reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0][0]
        closest_color = self.colors[0]
        colsest_color_dist = hue_distance(self.ground_truth_hsv[0][0], this_color_hsv[0])
        for idx, this_color in enumerate(self.colors):
            if hue_distance(self.ground_truth_hsv[idx][0], this_color_hsv[0]) < colsest_color_dist:
                colsest_color_dist = hue_distance(self.ground_truth_hsv[idx][0], this_color_hsv[0])
                closest_color = this_color
        if closest_color in confusing_set:
            target_color = random.choice(confusing_set)
        return self.drive_to_color(target_color, duration)

    def drive_to_color(self, color_name, duration=30):
        if color_name not in self.colors:
            print("unknown color")
            return False
        else:
            logger.debug("Driving to color: " + color_name)
            hsv = np.array(self.ground_truth_hsv[self.colors.index(color_name)])
            return self.drive_to_hsv(hsv, duration)

    def drive_to_hsv(self, target_hsv, duration=30):
        self.rot.setWalk(False)
        arrived_count = 0
        detect_color = False
        in_free_zone = 0
        startTime = time.time()
        pid_controller = PID(0.01, 0.01, 0.5)
        self.actual_rw_dir = "s"

        #check if the robot is in white free zone
        while in_free_zone < 3 and time.time() - startTime < duration:

            logger.debug("Driving to color: " + "in free zone")
            _, tag_height = self.check_apriltag()
            if tag_height > 0:
                # print(np.mean(newValues), newValues)
                if tag_height < 100:  # see white board ground
                    in_free_zone += 1

                else:
                    in_free_zone = 0
                    self.random_walk_engine(10, 7)
            else:
                self.random_walk_engine(10, 7)
                in_free_zone += 1

        lose_track_count = 0
        while arrived_count < 2 and time.time() - startTime < duration:
            #newValues = self.gs.getAvg()
            _, tag_height = self.check_apriltag()
            if tag_height>0:
                #print(tag_height)
                if tag_height >= 100 and detect_color:  # see color and white board at once
                    self.rot.setDrivingMode("pattern")
                    self.rot.setWalk(False)
                    arrived_count += 1
                else:
                    arrived_count = 0
            image = self.cam.get_reading()
            image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            tracking_color_threshold = color_hsv_threshold.copy()
            tracking_color_threshold[0]=15 #use wider threshold when tracking color
            cnt, cen = get_contours(image_hsv, target_hsv, tracking_color_threshold)
            if cen != -1 and cv2.contourArea(cnt) < 1000:
                cen = -1
            if cen != -1:
                detect_color = True
            else:
                detect_color = False
            self.last_speed = [0,0]
            if detect_color:
                lose_track_count=0
                self.rot.setDrivingMode("speed")
                error = 480 // 2 - cen
                dt = 1  # You can calculate the actual time difference between the frames for a more accurate control
                speed_adjustment = pid_controller.compute(error, dt)

                base_speed = self.max_speed*0.8

                left_speed = base_speed - speed_adjustment
                right_speed = base_speed + speed_adjustment
                self.last_speed = [left_speed, right_speed]
                # print("error: ", error, "set speeds: ", left_speed, right_speed)
                self.rot.setDrivingSpeed(left_speed,right_speed)
            elif arrived_count == 0 and lose_track_count<5:
                lose_track_count+=1
                self.rot.setDrivingSpeed(self.last_speed[1], self.last_speed[0]) #reverse last PID action, try to recover the color
            elif arrived_count == 0 and lose_track_count>=5:
                self.rot.setDrivingMode("pattern")
                pid_controller = PID(0.01, 0.01, 0.5) #reset controller
                self.random_walk_engine()
                #     self.rot.setPattern("s", 5)
                # elif dir_ang <= -1 and self.rot.isWalking() == False:
                #     # object not found, random walk
                #     walk_dir = random.choice(["s", "cw", "ccw"])
                #     self.rot.setPattern(walk_dir, 3)
                # elif dir_ang > 0:
                #     #print("cur angle: ", dir_ang)
                #     walk_time = np.ceil(1 + int(dir_ang))
                #     self.rot.setPattern("cw", walk_time)
                # elif dir_ang < 0:
                #     #print("cur angle: ", dir_ang)
                #     walk_time = np.ceil(1 - int(abs(dir_ang)))
                #     self.rot.setPattern("ccw", walk_time)
        self.rot.setDrivingMode("pattern")

        self.rot.setWalk(False)
        if arrived_count == 2:
            return True
        else:
            return False


    def get_color_list(self):
        return self.colors

    def set_leds(self, state):
        self.rot.setLEDs(state)

    def stop(self):
        self.rot.setWheels(0,0)
        self.rot.setWalk(False)
        #self.gs.stop()


if __name__ == "__main__":

    cwe = ColorWalkEngine(500)
    
    cwe.check_all_color()


    # print(cwe.discover_color(60)[1])
    # print(cwe.drive_to_color(cwe.discover_color(60)[1], duration=300))
    # tag_id = cwe.check_apriltag()
    # print(tag_id)
    # while tag_id == -1:
    #    tag_id = cwe.check_apriltag()
    #    print(tag_id)
