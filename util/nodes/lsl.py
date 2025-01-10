from pylsl import StreamInlet, resolve_stream, local_clock
import numpy as np
import asyncio
import os 

from .util.messages import SampleMessage
#from .util.rate import Rate
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
        assert(ch_names[-1] == 'SampleCounter')
        # check that sampling rate matches expected
        assert(info.nominal_srate() == self.config.sfreq)
        self.srate = info.nominal_srate()
        self.ch_names = ch_names
        os.mkdir(self.config.log_name)

    def write_chunk(self, chunk):
        idx = chunk[0][-1] # count of first sample in chunk
        f = os.path.join(self.config.log_name, '%d.npy'%idx)
        np.save(f, np.array(chunk), allow_pickle = False)

    @lg.publisher(OUTPUT)
    async def lsl_subscriber(self) -> lg.AsyncPublisher:
        #rate = Rate(self.config.sfreq)
        while True:
            chunk, timestamps = self.inlet.pull_chunk()
            if timestamps:
                offset = self.inlet.time_correction() # map timestamp to local clock
                for sample, t in zip(chunk, timestamps):
                    if sample[-1] % self.config.downsample == 0:
                        t += offset
                        x = sample[1] - sample[0] # reference EP1_pos to EP1_neg
                        x = x / (50 * 1000) # convert (gain 50)*V to mV
                        yield self.OUTPUT, SampleMessage(timestamp = t, data = np.array([x]))
                self.write_chunk(chunk)
            await asyncio.sleep(1./self.config.sfreq)
