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
    play_until: float = 0. # will play sounds until this time on LSL local_clock
    trial_type: str = 'systole'
    A_hz: float = 1000.
    B_hz: float = 500.

class ExperimentConfig(lg.Config):
    trials: int = 10
    kb_name: str = 'Dell Dell USB Keyboard'
    buffer_size: int = 5 # of IBIs to average over when caculating HR
    trial_duration: float = 10. # seconds

class Experiment(lg.Node):
    """
    This node runs the participant-facing experiment task in psychopy.
    """
    QRS_TOPIC = lg.Topic(FloatMessage)

    state: ExperimentState
    config: ExperimentConfig

    def setup(self) -> None: # anything involving graphics is set up in .main()
        self.state.t_of_last_R = local_clock()
        self.state.ibis = deque([], self.buffer_size)
        self.kb = get_keyboard(self.config.kb_name)

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

    @lg.subscriber(QRS_TOPIC)
    def update(self, message: DisplayMessage) -> None:
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
        self.play_sequence(t)

    def play_sequence(self, start_t):
        '''
        plays
        '''
        A = self.state.A_Hz
        B = self.state.B_Hz
        if local_clock() > self.state.play_until:
            return # don't play any sounds....
        ibi = self.IBI
        if 'systole' in self.state.trial_type:
            th = 1/6 # 1/6*ibi is about 1/2 systole
            offsets = [(th+3/4)*ibi, (th+1)*ibi, (th+1/4)*ibi]
        elif 'diastole' in self.state.trial_type:
            offsets = [(th+1/4)*ibi, (th+1/2)*ibi, (th+3/4)*ibi]
        already_elapsed = local_clock() - start_t
        R = ptb.GetSecs() - already_elapsed # start time on PTB clock
        if 'disc' in self.state.trial_type:
            # play a single sound for discrimnation task
            snd = Sound(B, secs = .1)
            snd.play(when = r + offsets[1]) # try to hit middle of target phase
            return
        # if not discrimination task, then play full ABA sequence
        sounds = []
        for hz in [A, B, A]:
            # set sound duration such that there's a 50ms gap between sounds
            sounds.append(Sound(hz, secs = ibi/4 - .050))
        for snd, offset in zip(sounds, offsets):
            # and then schedule playuback for target cardiac phases
            snd.play(when = R + offset) # schedule sounds

    def streaming_trial(self, A_freq, cardiac_phase):
        # set trial configuration
        self.state.A_hz = A_freq
        self.state.trial_type = '%s_streaming'%cardiac_phase
        # signal listening thread to play sounds until trial duration elapsed
        self.state.play_until = local_clock() + self.config.trial_duration
        # and wait here until sounds are done playing
        ptb.WaitSecs(self.config.trial_duration + 1.)
        return

    def discrimination_trial(self, cardiac_phase):
        # set trial configuration
        self.state.trial_type = '%s_discrimination'%cardiac_phase
        # signal listening thread to play sounds until trial duration elapsed
        self.state.play_until = local_clock() + self.config.trial_duration
        # and wait here until sounds are done playing
        ptb.WaitSecs(self.config.trial_duration + 1.)
        return

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

        # orient the subject
        #show_opening_instructions(win, self.kb)
        ptb.WaitSecs(6.)
        for trial in range(self.config.trials//2):
            self.streaming_trial(1000., 'systole')
        for trial in range(self.config.trials//2):
            self.streaming_trial(1000., 'diastole')


        #show_closing_instructions(win, self.kb)
        win.close()
        raise lg.NormalTermination()
