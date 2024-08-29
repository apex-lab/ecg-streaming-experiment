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
    trial_on: bool = False

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
        running mean of inter-beat intervals
        '''
        return np.median(self.state.ibis)

    @lg.subscriber(INPUT)
    async def update(self, message: FloatMessage) -> None:
        """
        Subscribes to R-peak event
        """
        t = message.timestamp
        ibi = t - self.state.t_of_last_R
        self.state.ibis.append(ibi) # add to buffer
        self.state.t_of_last_R = t
        self.state.detected = True # signal main thread

    def wait_until_detected(self, reset = True):
        '''
        waits for an R-peak until one is detected, and 
        returns time of R-peak on PTB clock
        '''
        if reset:
            self.state.detected = False 
        while not self.state.detected:
            continue
        self.state.detected = False # always resets after 
        t = self.state.t_of_last_R # time of R-peak on LSL clock
        already_elapsed = local_clock() - t
        t = ptb.GetSecs() - already_elapsed # time of R-peak on PTB clock
        return t

    def streaming_trial(self, phase = 'systole', A = 750, B = 500):

        print(phase)

        th = 1/6 # middle of systole as a proportion of R-R interval
        ibi = self.IBI
        dur = ibi/8 # minus space in between stimuli
        A1 = Sound(A, secs = dur)
        B1 = Sound(B, secs = dur)
        A2 = Sound(A, secs = dur)

        t0 = ptb.GetSecs()
        t = self.wait_until_detected() # time of R peak
        while ptb.GetSecs() < (t0 + self.config.trial_duration):
            #t = self.wait_until_detected() # time of R peak
            ibi = self.IBI
            if phase == 'systole': # aim for B to be in middle on next systole
                offsets = [(th+3/4)*ibi, (th+4/4)*ibi, (th+5/4)*ibi]
            elif phase == 'diastole': # aim for all tones to come after next systole
                # (could also try before next R-peak, but 
                # timing is tight for very fast heart rates)
                offsets = [(th+5/4)*ibi, (th+6/4)*ibi, (th+7/4)*ibi]
            A1.play(when = t + offsets[0])
            B1.play(when = t + offsets[1])
            A2.play(when = t + offsets[2])
            ptb.WaitSecs('YieldSecs', t + offsets[2] + dur - ptb.GetSecs())
            A1.stop()
            B1.stop()
            A2.stop()
            t += self.IBI
            
        self.wait_until_detected()
        return dict(A_hz = A, tone_duration = dur)
            
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
