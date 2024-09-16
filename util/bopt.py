from questplus import QuestPlus
import numpy as np

class FrequencyStaircase:
    '''
    A wrapper around questplus.QuestPlus that handles octave (i.e. log2)
    stimulus scaling and knows what 'streaming' and 'coherent' mean.

    We should use one staircase per
    '''

    def __init__(self, freq_range = [500, 5000]):

        # stimulus domain
        a0 = np.log2(freq_range[0]) # convert to octave/logartihmic scaling
        a1 = np.log2(freq_range[1])
        self.pitches = np.linspace(a0, a1, 100)
        stim_domain = dict(intensity = self.pitches)

        # Parameter domain.
        mus = self.pitches.copy()
        sigmas = np.linspace(0.1, 3, 30)
        param_domain = dict(
            mean = mus,
            sd = sigmas
        )

        # Outcome (response) domain.
        responses = ['streaming', 'coherent']
        outcome_domain = dict(response = responses)

        # Quest+ parameters.
        psychometric_func = 'norm_cdf'
        stim_scale = 'linear' # internal to prep, we will manually scale by log2
        stim_selection_method = 'min_entropy'
        param_estimation_method = 'mean'

        self.q = QuestPlus(
            stim_domain = stim_domain,
            func = psychometric_func,
            stim_scale = stim_scale,
            param_domain = param_domain,
            outcome_domain = outcome_domain,
            stim_selection_method = stim_selection_method,
            param_estimation_method = param_estimation_method
        )

    def update(self, trial_info):
        '''
        updates psychometric model params given one of the `info` dictionaries
        that `Experiment.streaming_trial` and `Experiment.streaming_trial`
        output.
        '''
        A_pitch = np.log2(trial_info['A_hz'])
        A_pitch = self.pitches[np.argmin(np.abs(self.pitches - A_pitch))]
        last_stim = dict(intensity = A_pitch)
        resp = dict(response = trial_info['response'])
        self.q.update(stim = last_stim, outcome = resp)
        return

    def get_next_freq(self):
        '''
        returns the frequency to play next trial in Hz
        '''
        return np.power(2, 1.*self.q.next_stim['intensity'])
