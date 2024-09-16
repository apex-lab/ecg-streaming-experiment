from typing import Tuple
from time import strftime
from typing import Dict
from os import path as op

from util.nodes.lsl import LSLPollerNode, LSLPollerConfig
from util.nodes.sim import ECGSimulator, ECGConfig
from util.nodes.bandpass import BandPass, BandPassConfig
from util.nodes.qrs import QRSDetector, QRSDetectorConfig
from experiment import Experiment, ExperimentConfig
import labgraph as lg

t0 = strftime('%Y%m%d-%H%M%S')


SIMULATE = False
ECG_CHANNEL = 1     # channel of LSL stream to use as ECG
SFREQ = 100.        # desired sampling rate
POLLING_RATE = 1000. # lowest hardware rate of TMSi SAGA

if SIMULATE:
    ecg_args = dict(sfreq = SFREQ)
    ECGNode = ECGSimulator
    ECGConfig = ECGConfig
    convert = False
else:
    downsample = POLLING_RATE / SFREQ
    assert(int(downsample) == downsample) # can only downsample by integer
    ecg_args = dict(
        sfreq = POLLING_RATE,
        downsample = int(downsample)
    )
    ECGNode = LSLPollerNode
    ECGConfig = LSLPollerConfig
    convert = True # convert units from microvolts to mV in filter node

class Graph(lg.Graph):

    GENERATOR: ECGNode
    FILTER: BandPass
    DETECTOR: QRSDetector
    EXPERIMENT: Experiment

    def setup(self) -> None:

        self.GENERATOR.configure(
            ECGConfig(**ecg_args)
        )
        self.FILTER.configure(
            BandPassConfig(
                low_cutoff = 5.,
                high_cutoff = 15.,
                sfreq = SFREQ,
                ch_idx = ECG_CHANNEL,
                #convert_microV_to_mV = convert
            )
        )
        self.DETECTOR.configure(
            QRSDetectorConfig(
                sfreq = SFREQ
            )
        )
        self.EXPERIMENT.configure(
            ExperimentConfig(
                trials = 10, # per task, across both systole and diastole
                kb_name = 'Darfon HP Wired Desktop 320K Keyboard',
                log_name = op.abspath(op.join('logs', t0 + '.tsv'))
            )
        )

    # Connect outputs to inputs
    def connections(self) -> lg.Connections:
        return (
            (self.GENERATOR.OUTPUT, self.FILTER.INPUT),
            (self.FILTER.OUTPUT, self.DETECTOR.INPUT),
            (self.DETECTOR.OUTPUT, self.EXPERIMENT.INPUT),
        )

    # Parallelization: Run nodes in separate processes
    def process_modules(self) -> Tuple[lg.Module, ...]:
        return (self.GENERATOR, self.FILTER, self.DETECTOR, self.EXPERIMENT)

    def logging(self) -> Dict[str, lg.Topic]:
        return {
            'ecg_raw': self.GENERATOR.OUTPUT,
            'ecg_filt': self.FILTER.OUTPUT,
            't_since': self.DETECTOR.OUTPUT,
            #'experiment_events': self.DISPLAY.EXPERIMENT_EVENTS,
            }

if __name__ == "__main__":
    sub_num = input('Enter subject number: ')
    sub_num = int(sub_num)
    sub = '%02d'%sub_num
    graph = Graph()
    options = lg.RunnerOptions(
        logger_config = lg.LoggerConfig(
            output_directory = './logs', # label has subject number and datetime
            recording_name = 'sub-%s_%s'%(sub, t0),
        ),
    )
    runner = lg.ParallelRunner(graph = graph, options = options)
    runner.run()
