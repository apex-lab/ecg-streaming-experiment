from dataclasses import field
from itertools import product
from typing import List, Tuple, Deque
from collections import deque
import numpy as np
import asyncio
import time
from pylsl import local_clock
from time import strftime
from util.logging import TSVLogger
from util.events import EventMarker

# force psychtoolbox audio backend so sounds can be scheduled
from psychopy.sound.backend_ptb import SoundPTB as Sound
from psychopy import monitors, visual, core
import psychtoolbox as ptb
from util.ui.display import (
    show_opening_instructions,
    show_midpoint_instructions,
    show_closing_instructions,
    solicit_2AFC_streaming,
    solicit_2AFC_discrimination,
    fixation_cross
)
from util.ui.input import get_keyboard
from util.bopt import FrequencyStaircase

from util.nodes.util.messages import FloatMessage
import labgraph as lg

EVENT_CODES = dict(
    streaming_systole = 11,
    streaming_diastole = 12,
    discrimination_systole = 21,
    discrimination_diastole = 22
)

class ExperimentState(lg.State):
    ibis: Deque[float] = None
    t_of_last_R: float = None
    trial_type: str = 'systole'
    detected: bool = False
    trial_on: bool = False

class ExperimentConfig(lg.Config):
    trials: int = 10 # per task, across both trial types (systole and diastole)
    kb_name: str = 'Dell Dell USB Keyboard'
    buffer_size: int = 10  # of IBIs to average over when caculating HR
    trial_duration: float = 10. # seconds
    log_name: str = None
    vol: float = None


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
        if self.config.log_name is None: # default is time of Experiment init  
            self.config.log_name = strftime('%Y%m%d-%H%M%S') + '.tsv'
        self.marker = EventMarker() # sends triggers to brainvision amp

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

    def play_tones(self, trial_type, phase, A = 750, B = 500):
        '''
        Cues tones to be played for every R-peak until the trial duration
        elapses, then waits until the next R-peak to return.
        '''

        self.marker.send(EVENT_CODES['%s_%s'%(trial_type, phase)])

        th = 1/6 # middle of systole as a proportion of R-R interval
        ibi = self.IBI
        dur = ibi/8 # minus space in between stimuli
        assert(np.isfinite(ibi))
        A1 = Sound(A, secs = dur, volume = self.config.vol)
        B1 = Sound(B, secs = dur, volume = self.config.vol)
        A2 = Sound(A, secs = dur, volume = self.config.vol)

        t0 = ptb.GetSecs()
        t = self.wait_until_detected() # time of R peak
        while ptb.GetSecs() < (t0 + self.config.trial_duration):
            ibi = self.IBI#self.state.ibis[-1]
            if phase == 'systole': # aim for B to be in middle on next systole
                offsets = [(th+3/4)*ibi, (th+4/4)*ibi, (th+5/4)*ibi]
            elif phase == 'diastole': # aim for all tones to come after next systole
                # (could also try before next R-peak, but
                # timing is tight for very fast heart rates)
                offsets = [(th+5/4)*ibi, (th+6/4)*ibi, (th+7/4)*ibi]
            if trial_type == 'streaming':
                A1.play(when = t + offsets[0])
                B1.play(when = t + offsets[1])
                A2.play(when = t + offsets[2])
            elif trial_type == 'discrimination':
                B1.play(when = t + offsets[1])
            ptb.WaitSecs('YieldSecs', t + offsets[-1] + dur - ptb.GetSecs())
            t += self.state.ibis[-1]
            A1.stop()
            B1.stop()
            A2.stop()
        
        self.wait_until_detected()
        info = dict(
            trial = trial_type,
            cardiac_phase = phase,
            A_hz = A, B_hz = B,
            tone_duration = dur
        )
        return info

    def streaming_trial(self, win, kb, phase, A = 750):
        t0 = local_clock() # on LSL clock, so it can be aligned with physio
        fixation_cross(win) # displays until next screen flip...
        ptb.WaitSecs('YieldSecs', .5)
        info = self.play_tones('streaming', phase, A)
        t1 = local_clock()
        resp = solicit_2AFC_streaming(win, kb) # this is the next screen flip.
        info['response'] = resp
        info['onset'] =  t0
        info['duration'] = t1 - t0
        return info

    def discrimination_trial(self, win, kb, phase):
        t0 = local_clock()
        fixation_cross(win)
        ptb.WaitSecs('YieldSecs', .5)
        info = self.play_tones('discrimination', phase)
        t1 = local_clock()
        resp = solicit_2AFC_discrimination(win, kb)
        info['response'] = resp
        info['onset'] =  t0
        info['duration'] = t1 - t0
        del info['A_hz'] # because only B tone was presented
        return info

    @lg.main # decorator indicates always to be run in main thread
    def experiment(self):
        '''
        This is the main experiment code. Any graphics-related objects need to
        be set up here, since graphics need to be handled from the main thread.
        '''
        kb = get_keyboard(self.config.kb_name)
        win = visual.Window( # must be started here in main thread
            size = [1920, 1080],
            fullscr = False,
            allowGUI = False,
            screen = -1,
            units = 'pix',
        )

        log = TSVLogger(self.config.log_name)

        # orient the subject
        show_opening_instructions(win, kb)

        n_trials = self.config.trials
        trials = (n_trials//2 * ['systole']) + (n_trials//2 * ['diastole'])
        np.random.shuffle(trials) # pseudo-random trial order
        staircases = dict(
            systole = FrequencyStaircase(), # use Bayesian staircase to
            diastole = FrequencyStaircase() # select A-tone frequencies
        )
        for phase in trials:
            hz = staircases[phase].get_next_freq()
            trial_info = self.streaming_trial(win, kb, phase, A = hz)
            staircases[phase].update(trial_info)
            log.write(**trial_info)

        show_midpoint_instructions(win, kb)

        np.random.shuffle(trials)
        for phase in trials:
            trial_info = self.discrimination_trial(win, kb, phase)
            log.write(**trial_info)

        del log # closes log file

        show_closing_instructions(win, kb)
        win.close()
        self.marker.close()
        raise lg.NormalTermination()
