#!/usr/bin/env python3
import time
#from aenum import Enum, auto

class Idle():
    IDLE   = 1

class Scout():
    Query    = 2
    PrepReport = 3

class Verify():
    DriveTo = 4
    PrepReport = 5



class FiniteStateMachine(object):

    def __init__(self, start = None):
        self._prevState = start
        self._currState = start
        self._accumTime = dict()
        self._startTime = time.time()

    def getPreviousState(self):
        return self._prevState

    def getState(self, ):
        return self._currState

    def getTimers(self):
        return self._accumTime

    def setState(self, state, message = ""):

        self.onTransition(state, message)

        if self._currState not in self._accumTime:
            self._accumTime[self._currState] = 0

        self._accumTime[self._currState] += time.time() - self._startTime
        self._prevState = self._currState
        self._currState = state
        self._startTime = time.time()
    
    def query(self, state, previous = False):
        if previous:
            return self._prevState == state
        else:
            return self._currState == state

    def onTransition(self, state, message):
        # Robot actions to perform on every transition
        pass
        # if message != None:
        #     self.robot.log.info("%s -> %s%s", self._currState, state, ' | '+ message)
        #

