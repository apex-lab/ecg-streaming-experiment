from pylsl import StreamInlet, resolve_stream
import numpy as np
import asyncio

from .util.messages import SampleMessage
from .util.rate import Rate
import labgraph as lg


class LSLPollerConfig(lg.Config):
    type: str = 'EEG'
    sfreq: float = 500.
    downsample: int = 1

class LSLPollerNode(lg.Node):

    OUTPUT = lg.Topic(SampleMessage)
    config: LSLPollerConfig

    def setup(self) -> None:
        self._shutdown = False

    def setup(self) -> None:
        self.streams = resolve_stream('type', self.config.type)
        self.inlet = StreamInlet(self.streams[0])
        # check that first channel is EP preamp
        info = self.inlet.info()
        ch = info.desc().child('channels').child('channel')
        assert(ch.child_value('label') == 'EP1_neg')
        # check that sampling rate matches expected
        assert(info.nominal_srate() == self.config.sfreq)

    @lg.publisher(OUTPUT)
    async def lsl_subscriber(self) -> lg.AsyncPublisher:
        rate = Rate(self.config.sfreq)
        count = 0
        while True:
            sample, t = self.inlet.pull_sample()
            t += self.inlet.time_correction() # map timestamp to local clock
            if t is not None:
                count += 1
                if count % self.config.downsample == 0:
                    x = np.array(sample)
                    x[1] = x[1] - x[0] # reference EP1_pos to EP1_neg
                    x[1] = x[1] / (50 * 1000) # convert (gain 50)*V to mV
                    yield self.OUTPUT, SampleMessage(timestamp = t, data = x)
                await rate.sleep()
