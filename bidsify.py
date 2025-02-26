import pandas as pd
import numpy as np
import os
import re
import json

from mne_bids import BIDSPath, write_raw_bids, make_dataset_description
import mne

SOURCE_DIR = os.getcwd()
BIDS_ROOT = 'bids_dataset'

SRATE = 10000
AMP_GAIN = 50
AUDIO_GAIN = 100
LINE_FREQ = 60.


def reformat_events(events, timestamp, triggers):
    tone_infos = []
    for i in range(events.shape[0]):
        trial_onset = events.onset.iloc[i]
        trial_end = trial_onset + events.duration.iloc[i] 
        during_trial = np.logical_and(trial_onset < timestamp, timestamp < trial_end)
        tone_onsets = timestamp[np.logical_and(during_trial, triggers == 128)]
        A_hz = events.A_hz.iloc[i]
        B_hz = events.B_hz.iloc[i]
        trial_type = events.trial.iloc[i]
        if trial_type == 'streaming':
            # if tones don't come in triplets,
            # something went wrong....
            try:
                assert(tone_onsets.size % 3 == 0)
            except:
                continue # skip this trial, since we aren't sure delivered correctly
                #raise Exception('%d tones in trial %d!'%(tone_onsets.size, i+1))
        tone_names = ['A', 'B', 'A'] if trial_type == 'streaming' else ['B']
        for j, onset in enumerate(tone_onsets):
            tone = tone_names[j % len(tone_names)]
            info = dict(
                onset = onset,
                duration = events.tone_duration.iloc[i],
                trial_num = i + 1,
                trial_type = events.cardiac_phase.iloc[i],
                tone_num = j + 1,
                tone_type = tone,
                frequency = A_hz if tone == 'A' else B_hz,
                response = events.response.iloc[i]
            )
            tone_infos.append(info)
    return pd.DataFrame(tone_infos)


def format_eeg(data, events, idx):
    t = np.arange(data.shape[0])/SRATE
    data = data[idx, :]
    t0 = t[idx][0]
    events.onset -= t0
    ecg = (data[:, 1] - data[:, 0]) / (2*AMP_GAIN)
    eeg = (data[:, 3] - data[:, 2]) / (2*AMP_GAIN)
    audio = data[:, 4] / AUDIO_GAIN
    info = mne.create_info(
        ch_names = ['Fz', 'ecg', 'audio'],
        ch_types = ['eeg', 'ecg', 'misc'],
        sfreq = SRATE
    )
    data = np.stack([eeg, ecg, audio], axis = 0)
    raw = mne.io.RawArray(data*1e-6, info) # input in Volts
    raw.info['line_freq'] = LINE_FREQ
    return raw, events


def write_to_bids(sub, task, raw, events, root = BIDS_ROOT):
    # make BIDS directory for sub if doesn't exist
    bids_path = BIDSPath(subject = sub, task = task, root = root)
    # write EEG data to disk
    write_raw_bids(
        raw,
        bids_path,
        overwrite = True,
        allow_preload = True,
        format = 'BrainVision'
    )
    # write events file
    evf = str(bids_path).replace('_eeg.vhdr', '_events.tsv')
    events.to_csv(evf, sep = '\t', index = False, na_rep = 'n/a')
    # write json sidecar for events
    info = dict()
    info['trial_num'] = {'Description': 'Trial number of tone sequence'}
    info['trial_type'] = {
        'Description': 'Experimental condition of tone sequence',
        'Levels': {
            'systole': 'B tones were presented during ventricular systole',
            'diastole': 'B tones were presented during ventricular diastole'
        }
    }
    info['tone_num'] = {'Description': 'Order of tone within sequence'}
    info['tone_type'] = {'Description': 'Type of tone within sequence'}
    if task == 'streaming':
        info['tone_type']['Levels'] = {
            'A': 'A in ABA- sequence.',
            'B': 'B in ABA- sequence.'
        }
    else:
        info['tone_type']['Levels'] = {
            'B': 'Identical to the B tones in the streaming task.'
        }
    info['frequency'] = {'Description': 'Acoustic frequency of tone in Hz'}
    info['response'] = {'Description': 'Participant response'}
    if task == 'streaming':
        info['response']['Levels'] = {
            'coherent': 'Participant heard unified ABA- sequence',
            'streaming': 'Participant heard two separate A- and B- streams.'
        }
    else:
        info['response']['Levels'] = {
            'systole': 'Participant thought tones were synchronized to their heartbeat',
            'diastole': 'Participant thought tones were presented between heartbeats'
        }
    scf = evf.replace('_events.tsv', '_events.json')
    with open(scf, 'w') as f:
        info = json.dump(info, f, indent = 4)
    # edit json sidecar for EEG
    scf = evf.replace('_events.tsv', '_eeg.json')
    with open(scf, 'r') as f:
        info = json.load(f)
    info['EEGReference'] = 'left mastoid'
    info['EEGGround'] = 'right mastoid'
    info['ManufacturersModelName'] = 'actiCHamp Plus with EP-PreAmp Gain 50'
    with open(scf, 'w') as f:
        info = json.dump(info, f, indent = 4)



def main(sub, sub_timestamp):

    # find participant's files
    log_fpath = os.path.join(SOURCE_DIR, 'logs', '%s.tsv'%sub_timestamp)
    eeg_dir = os.path.join(SOURCE_DIR, 'eeg', sub_timestamp)
    eeg_fs = [os.path.join(eeg_dir, f) for f in os.listdir(eeg_dir)]
    sample_count = lambda f: int(re.findall(r'%s(\w+).npy'%os.sep, f)[0])
    eeg_fs.sort(key = sample_count)

    ## load data
    data = np.concatenate([np.load(f) for f in eeg_fs])
    timestamp = np.arange(data.shape[0])/SRATE
    triggers = data[:, 5]
    sample_count = data[:, 6]
    # make sure samples are sorted in temporal order
    is_sorted = lambda a: np.all(a[:-1] <= a[1:])
    assert(is_sorted(sample_count))
    # and event info
    events = pd.read_csv(log_fpath, sep = '\t')
    trials = idxs = np.where(np.isin(triggers, [11, 12, 21, 22]))[0]
    t = timestamp[trials]
    events['onset'] = t # merge in EEG event times
    events['trigger'] = triggers[trials].astype(int)
    # double check trigger codes align correctly with log file
    syst = events.trigger % 2 == 1
    assert((events[syst].cardiac_phase == 'systole').mean() == 1)
    stream = events.trigger < 20
    assert((events[stream].trial == 'streaming').mean() == 1)

    ## reformat event dataframe so there's an event for each tone
    # and the tasks are in seperate dataframes
    stream = reformat_events(events[events.trial == 'streaming'], timestamp, triggers)
    disc = reformat_events(events[events.trial == 'discrimination'], timestamp, triggers)
    # recode participant responses to something meaningful
    disc.replace({'yes': 'systole', 'no': 'diastole'}, inplace = True)

    # pick a time to split recording between tasks
    streaming_ends = stream.onset.iloc[-1] + stream.duration.iloc[-1]
    discrimination_begins = disc.onset.iloc[0]
    cutoff = (streaming_ends + discrimination_begins) / 2
    # and do so...
    raw_stream, evs_stream = format_eeg(data, stream, timestamp < cutoff)
    raw_disc, evs_disc = format_eeg(data, disc, timestamp > cutoff)

    ## now write data to BIDS directory!
    write_to_bids(sub, 'streaming', raw_stream, evs_stream)
    write_to_bids(sub, 'discrimination', raw_disc, evs_disc)

    ## and make dataset description file in case doesn't already exist
    make_dataset_description(
        path = BIDS_ROOT,
        name = 'Auditory Streaming and Interoception',
        authors = ['John Veillette', 'Aditi Joshi', 'Ying Li', 'Howard Nusbaum'],
        data_license = 'CC0',
        ethics_approvals = ['University of Chicago Social & Behavioral Sciences IRB24-1904'],
        funding = ['NSF BCS 2024923'],
        overwrite = True
    )


if __name__ == "__main__":
    log_dir = os.path.join(SOURCE_DIR, 'logs')
    log_fs = os.listdir(log_dir)
    labgraph_logs = [f for f in log_fs if '.h5' in f]
    sub_ids = {
        int(re.findall(r'sub-(\w+)_', f)[0]): re.findall(r'_(\w+-\w+).h5', f)[0]
        for f in labgraph_logs
    }
    sub_nums = [s for s in sub_ids]
    sub_nums.sort()
    for s in sub_nums:
        sub = '%02d'%s
        timestamp = sub_ids[s]
        print('Starting sub-%s...'%sub)
        main(sub, timestamp)
