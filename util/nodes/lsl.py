from pylsl import StreamInlet, resolve_stream, local_clock
import numpy as np
import asyncio

from .util.messages import SampleMessage
from .util.rate import Rate
from ..logging import TSVLogger
import labgraph as lg


class LSLPollerConfig(lg.Config):
    type: str = 'EEG'
    sfreq: float = 500.
    downsample: int = 1
    log_name: str = None

class LSLPollerNode(lg.Node):

    OUTPUT = lg.Topic(SampleMessage)
    config: LSLPollerConfig

    def setup(self) -> None:
        self._shutdown = False

    def setup(self) -> None:
        self.streams = resolve_stream('type', self.config.type)
        self.inlet = StreamInlet(self.streams[0])
        info = self.inlet.info()
        ch_names = []
        ch = info.desc().child("channels").child("channel")
        for k in range(info.channel_count()):
            ch_names.append(ch.child_value("label"))
            ch = ch.next_sibling()
        # check that we have the right stream (i.e. first channel is preamp)
        assert(ch_names[0] == 'EP1_neg')
        assert(ch_names[1] == 'EP1_pos')
        # check that sampling rate matches expected
        assert(info.nominal_srate() == self.config.sfreq)
        self.ch_names = ch_names
        self.log = TSVLogger(self.config.log_name)


    @lg.publisher(OUTPUT)
    async def lsl_subscriber(self) -> lg.AsyncPublisher:
        rate = Rate(self.config.sfreq * 2)
        count = 0
        while True:
            sample, t = self.inlet.pull_sample()
            if t is not None:
                self.log.write(**{ # save all samples to file 
                    self.ch_names[i]: sample[i] 
                    for i in range(len(sample))
                })
                count += 1
                if count % self.config.downsample == 0:
                    t += self.inlet.time_correction() # map timestamp to local clock
                    x = sample[1] - sample[0] # reference EP1_pos to EP1_neg
                    x = x / (50 * 1000) # convert (gain 50)*V to mV
                    yield self.OUTPUT, SampleMessage(timestamp = t, data = np.array([x]))
                await rate.sleep()
