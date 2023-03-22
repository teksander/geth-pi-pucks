#!/usr/bin/env python3
import random, math
import time
import smbus
import threading
import logging

logging.basicConfig(format='[%(levelname)s %(name)s %(relativeCreated)d] %(message)s')
logger = logging.getLogger(__name__)


class Rotation(object):
    """ Set up a Random-Walk loop on a background thread
    The __walking() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(self, MAX_SPEED):
        """ Constructor
        :type range: int
        :param enode: Random-Walk speed (tip: 500)
        """
        self.MAX_SPEED = MAX_SPEED
        self.__stop = 1
        self.__walk = True
        self.__pattern = "s"
        self.duration = 1 #if duration == -1: run forever
        self.mode = "pattern" #pattern or speed
        self.left = 0
        self.right = 0 #left and right speed

        logger.info('Random-Walk OK')

    def __write_data(self, register, data):
        trials = 0
        while True:
            try:
                self.__bus.write_word_data(self.__i2c_address, register, data)
                return
            except:
                trials += 1
                time.sleep(0.1)
                if (trials == 5):
                    logger.error('RW I2C write error')
                    return

    def __read_data(self, register):
        trials = 0
        while True:
            try:
                return self.__bus.read_word_data(self.__i2c_address, register)
            except:
                trials += 1
                time.sleep(0.1)
                if (trials == 5):
                    logger.error('RW I2C read error')
                    return

    def __walking(self):
        """ This method runs in the background until program is closed """

        # Initialize I2C bus
        I2C_CHANNEL = 4
        EPUCK_I2C_ADDR = 0x1f
        self.__bus = smbus.SMBus(I2C_CHANNEL)
        self.__i2c_address = EPUCK_I2C_ADDR

        # Motor register addresses
        LEFT_MOTOR_SPEED = 2
        RIGHT_MOTOR_SPEED = 3

        # IR Sensors register addresses
        IR_CONTROL = 6
        IR0_REFLECTED = 7
        self.irDist = 200
        # LEDs
        OUTER_LEDS = 0
        self.__LEDState = 0b00000000
        self.__isLEDset = True  # Remove when Pi-puck2s are upgraded

        # rotation parameters
        #self.__pattern

        # Obstacle Avoidance parameters
        weights_left = [-8, -8, -3, 0, 0, 3, 8, 8]
        weights_right = [-1 * x for x in weights_left]

        # Turn IR sensors on
        self.__write_data(IR_CONTROL, 1)
        self.__write_data(OUTER_LEDS, self.__LEDState)

        while True:
            if self.__stop:
                # Stop IR and Motor
                break

            this_left = 0
            this_right = 0
            if self.mode == "pattern":
                if self.duration > 0 and self.duration != -1:
                    self.duration -= 1
                elif self.duration == 0:
                    self.__walk = False
                # Find Wheel Speed for Random-Walk
                if (self.__pattern == "cw"):
                    this_left = self.MAX_SPEED / 2
                    this_right = -self.MAX_SPEED / 2
                elif (self.__pattern == "ccw"):
                    this_left = -self.MAX_SPEED / 2
                    this_right  = self.MAX_SPEED / 2
                elif (self.__pattern == "s"):
                    this_left = self.MAX_SPEED / 2
                    this_right = self.MAX_SPEED / 2
                #print(self.__pattern, " set wheel speed to: ", this_left, this_right)
            elif self.mode == "speed":
                self.__walk = True
                this_left = self.left
                this_right = self.right

            # Obstacle avoidance

            self.ir = [0] * 8
            for i in range(8):
                self.ir[i] = self.__read_data(IR0_REFLECTED + i)
                #print("ir reading: ", self.ir[i])
                if not self.ir[i] or self.ir[i] > 50000:
                    self.ir[i] = 0

            # Find Wheel Speed for Obstacle Avoidance

            for i, reading in enumerate(self.ir):

                if (reading > self.irDist):
                    this_left  = self.MAX_SPEED / 2 + weights_left[i] * reading
                    this_right = self.MAX_SPEED / 2 + weights_right[i] * reading

            # Saturate Speeds greater than MAX_SPEED
            if this_left > self.MAX_SPEED:
                this_left  = self.MAX_SPEED
            elif this_left  < -self.MAX_SPEED:
                this_left  = -self.MAX_SPEED

            if this_right > self.MAX_SPEED:
                this_right = self.MAX_SPEED
            elif this_right < -self.MAX_SPEED:
                this_right = -self.MAX_SPEED
            #print(self.__pattern, " final wheel speed: ", this_left, this_right)
            if self.__walk:
                # Set wheel speeds
                self.__write_data(LEFT_MOTOR_SPEED, int(this_left))
                time.sleep(0.01)
                self.__write_data(RIGHT_MOTOR_SPEED, int(this_right))
                time.sleep(0.01)
            else:
                # Set wheel speeds
                self.__write_data(LEFT_MOTOR_SPEED, 0)
                time.sleep(0.01)
                self.__write_data(RIGHT_MOTOR_SPEED, 0)
                time.sleep(0.01)

            # Set the LED ring
            if not self.__isLEDset:  # Remove when Pi-puck2s are upgraded
                self.__write_data(OUTER_LEDS, self.__LEDState)
                self.__isLEDset = True

            if self.__stop:
                break
            else:
                time.sleep(0.1)

    def start(self):
        """ This method is called to start __walki            if (actual_direction == "straight"):
                left = right = self.MAX_SPEED / 2ng """
        if self.__stop:
            self.__stop = False
            # Initialize background daemon thread
            self.thread = threading.Thread(target=self.__walking)
            self.thread.daemon = True

            # Start the execution
            self.thread.start()
        else:
            logger.warning('Already Walking')

    def stop(self):
        """ This method is called before a clean exit """
        self.__stop = True
        self.thread.join()
        self.__write_data(6, 0)
        time.sleep(0.05)
        self.__write_data(2, 0)
        time.sleep(0.05)
        self.__write_data(3, 0)
        time.sleep(0.05)
        self.__write_data(0, 0b00000000)
        time.sleep(0.05)
        self.__bus.close()
        logger.info('Random-Walk OFF')

    def setWalk(self, state):
        """ This method is called set the random-walk to on without disabling I2C"""
        self.__walk = state
    def isWalking(self):
        return self.__walk
    def setPattern(self, pattern, duration):
        self.__pattern=pattern
        self.duration=duration
        if self.__walk == False:
            self.__walk = True
    def setDrivingSpeed(self, left, right):
        self.left = left
        self.right = right
    def setDrivingMode(self, mode):
        self.mode=mode
    def setWheels(self, left, right):
        """ This method is called set each wheel speed """
        # Set wheel speeds
        self.__write_data(2, int(left))
        time.sleep(0.01)
        self.__write_data(3, int(right))
        time.sleep(0.01)

    def setLEDs(self, state):
        """ This method is called set the outer LEDs to an 8-bit state """
        if self.__LEDState != state:
            self.__isLEDset = False
            self.__LEDState = state

    def getIr(self):
        """ This method returns the IR readings """
        return self.ir


if __name__ == "__main__":
    rot = Rotation(500)
    rot.start()
    input("any key to straight")
    rot.setPattern("s",100)
    input("any key to turn")
    rot.setPattern("cw", 100)
    input("any key to stop")
    rot.setPattern("ccw", 100)
    input("any key to stop")
    rot.setWalk(False)
    input("any key to disconnect")
    rot.stop()




