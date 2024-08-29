from dataclasses import field
from itertools import product
from typing import List, Tuple, Deque
from collections import deque
import numpy as np
import asyncio
import time
from pylsl import local_clock

# force psychtoolbox audio backend so sounds can be scheduled
from psychopy.sound.backend_ptb import SoundPTB as Sound
from psychopy import monitors, visual, core
import psychtoolbox as ptb
#from util.ui.instructions import (
#    show_opening_instructions,
    #show_break_instructions,
    #show_midpoint_instructions,
#    show_closing_instructions,
#    get_2AFC
#)
#from util.ui.input import get_keyboard

from util.nodes.util.messages import FloatMessage
import labgraph as lg

class ExperimentState(lg.State):
    ibis: Deque[float] = None
    t_of_last_R: float = None
    trial_type: str = 'systole'
    detected: bool = False

class ExperimentConfig(lg.Config):
    trials: int = 2
    kb_name: str = 'Dell Dell USB Keyboard'
    buffer_size: int = 10 # of IBIs to average over when caculating HR
    trial_duration: float = 10. # seconds
        

class Experiment(lg.Node):
    """
    This node runs the participant-facing experiment task in psychopy.
    """
    INPUT = lg.Topic(FloatMessage)

    state: ExperimentState
    config: ExperimentConfig

    def setup(self) -> None: # anything involving graphics is set up in .main()
        self.state.t_of_last_R = local_clock()
        self.state.ibis = deque([], self.config.buffer_size)
        #self.kb = get_keyboard(self.config.kb_name)

    def cleanup(self) -> None:
        """
        This function is called when a NormalTermination is raised, so we set
        relevant shutdown flags here. We can use this to break out of infinite
        loops.
        """
        self._shutdown = True

    @property
    def IBI(self):
        '''
        the mean of the interbeat interval over buffer
        '''
        return np.mean(self.state.ibis)

    @lg.subscriber(INPUT)
    def update(self, message: FloatMessage) -> None:
        """
        Subscribes to topic that gives time since last R-peak.
        """
        t = message.timestamp
        time_since_rpeak = message.data
        if time_since_rpeak != 0:
            return
        # if an R-peak was detected, update state
        ibi = t - self.state.t_of_last_R
        self.state.ibis.append(ibi) # add to buffer
        self.state.t_of_last_R = t
        # and then trigger next tones if during a trial
        self.state.detected = True

    def wait_until_detected(self):
        #self.state.detected = False # reset
        while not self.state.detected:
            continue#ptb.WaitSecs(.005)
        self.state.detected = False # reset
        t = self.state.t_of_last_R
        already_elapsed = local_clock() - t
        t = ptb.GetSecs() - already_elapsed # time of R-peak on PTB clock
        return t

    def streaming_trial(self, A = 1000., phase = 'systole'):
        print(phase)

        B = 500.

        th = 1/6 # middle of systole as a proportion of R-R interval
        ibi = self.IBI
        dur = ibi/4 - .12 # minus space in between stimuli
        A1 = Sound(A, secs = dur)
        B1 = Sound(B, secs = dur)
        A2 = Sound(A, secs = dur)

        self.state.detected = False # reset
        tt = ptb.GetSecs()
        while ptb.GetSecs() < (tt + self.config.trial_duration):
            t = self.wait_until_detected() # time of R peak
            ibi = self.IBI
            if phase == 'systole':
                offsets = [(th+3/4)*ibi, (th+1)*ibi, (th+5/4)*ibi]
            elif phase == 'diastole':
                offsets = [(th+1/4)*ibi, (th+1/2)*ibi, (th+3/4)*ibi]
            A1.play(when = t + offsets[0])
            B1.play(when = t + offsets[1])
            A2.play(when = t + offsets[2])
            ptb.WaitSecs('UntilTime', t + offsets[2] + dur)
            A1.stop()
            B1.stop()
            A2.stop()
        self.wait_until_detected()
            
    @lg.main
    def experiment(self):
        '''
        This is the main experiment code. Any graphics-related objects need to
        be set up here, since graphics need to be handled from the main thread.
        '''
        win = visual.Window( # must be started here in main thread
            size = [1920//4, 1080//4],
            fullscr = False,
            #allowGUI = False,
            #screen = -1,
            units = 'pix',
        )

        for i in range(10):
            self.wait_until_detected()
            print('det')
        ptb.WaitSecs(1.)
        self.streaming_trial(phase = 'systole')
        ptb.WaitSecs(1.)
        self.streaming_trial(phase = 'diastole')
        ptb.WaitSecs(1.)
        self.streaming_trial(phase = 'systole')
        ptb.WaitSecs(1.)
        self.streaming_trial(phase = 'diastole')
        
        # orient the subject
        #show_opening_instructions(win, self.kb)
        
        #for trial in range(self.config.trials//2):
        #    self.streaming_trial(1000., 'systole')
        #for trial in range(self.config.trials//2):
        #    self.streaming_trial(1000., 'diastole')


        #show_closing_instructions(win, self.kb)
        win.close()
        raise lg.NormalTermination()
