import cv2
import picamera
import os
from picamera.array import PiRGBArray
import logging

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)


def focusing(val):
    value = (val << 4) & 0x3ff0
    data1 = (value >> 8) & 0x3f
    data2 = value & 0xf0
    os.system("i2cset -y 0 0x0c %d %d" % (data1, data2))


def __laplacian(img):
    img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    img_sobel = cv2.Laplacian(img_gray, cv2.CV_16U)
    return cv2.mean(img_sobel)[0]

def calculation(camera):
    rawCapture = PiRGBArray(camera)
    camera.capture(rawCapture, format="bgr", use_video_port=True)
    image = rawCapture.array
    rawCapture.truncate(0)
    return __laplacian(image)


class UpCamera(object):
    """ set up an camera object for the R0176 Arducam camera.
    """
    def __init__(self, interesting_reg_h = 100, interesting_reg_offset = 50, rot = True):
        """ Constructor
        :type freq: str
        :param freq: frequency of measurements in Hz (tip: 20Hz)
        """
        self.__stop = 1
        self.camera = picamera.PiCamera()
        # set camera resolution to 640x480(Small resolution for faster speeds.)
        self.camera.resolution = (640, 480)
        self.interesting_region_h = interesting_reg_h
        self.interesting_region_o = interesting_reg_offset
        self.rotate = rot
        #find best focal distance
        self.focal_calibration()
        logger.info('Up-Camera OK')


    def focal_calibration(self):
        print("Start focusing")

        max_index = 10
        max_value = 0.0
        last_value = 0.0
        dec_count = 0
        focal_distance = 10
        while True:
            # Adjust focus
            focusing(focal_distance)
            # Take image and calculate image clarity
            val = calculation(self.camera)
            # Find the maximum image clarity
            if val > max_value:
                max_index = focal_distance
                max_value = val

            # If the image clarity starts to decrease
            if val < last_value:
                dec_count += 1
            else:
                dec_count = 0
            # Image clarity is reduced by six consecutive frames
            if dec_count > 6:
                break
            last_value = val

            # Increase the focal distance
            focal_distance += 10
            if focal_distance > 1000:
                break

        # Adjust focus to the best
        focusing(max_index)
        print("Set focal distance to: ", max_index)
    def get_reading(self):
        rawCapture = PiRGBArray(self.camera)
        self.camera.capture(rawCapture, format="bgr", use_video_port=True)
        image = rawCapture.array
        rawCapture.truncate(0)
        if self.rotate:
            image = cv2.rotate(image, cv2.ROTATE_180)
        #corp image according to the interesting region definition
        centre = image.shape
        cx = centre[1]/2 - 480/2
        cy = centre[0]/2- self.interesting_region_h/2 + self.interesting_region_o
        corp_img = image[int(cy):int(cy+self.interesting_region_h), int(cx):int(cx+480)]
        return corp_img

    def get_rgb_feature(self, length=10, interval=10):
        image=self.get_reading()
        image_sz = image.shape
        feature = []
        idx = int(length / 2)
        while idx + int(length / 2) < image_sz[1]:
            feature.append(image[:, idx - int(length / 2):idx + int(length / 2)].mean(axis=0))
            idx += interval
        return feature