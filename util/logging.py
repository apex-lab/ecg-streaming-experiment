import os

class TSVLogger:

    def __init__(self, fpath):
        '''
        Opens a TSV file in which to log experiment events.

        Parameters
        ----------
        fields : list of str
            Names of fields (columns) to be included in the log file.
        dir : str
            A relative directory path. This should be a root directory where all
            subjects' data is to be saved; a subject-specific subdirectory will
            be created within this root directory.
        '''
        self._f = open(fpath, 'w')
        self._fields = None

    def write_fields(self, params):
        self._fields = list(params)
        self._f.write('\t'.join(self._fields))

    def write(self, **params):
        '''
        Adds trial (meta)data to the TSV file line-by-line.

        Usage Example
        ----------
        You can write a TSV file line-by-line with the fields you specified
        when initializing the TSVLogger object.::

            log = TSVLogger(sub = '01', task = 'cfs', fields = ['trial','resp'])
            log.write(trial = 1, resp = 'yes')
            log.write(trial = 2) # response will be 'n/a'

        If you don't include a field specified at initialization, then it will
        be filled in with an 'n/a' automatically.
        '''
        if self._fields is None: # the first call will be used to determine
            self.write_fields(params) # the column names in the log file 
        vals = dict()
        for field in self._fields:
            if field in params:
                vals[field] = params[field]
            else:
                vals[field] = 'n/a'
        boilerplate = '\n' + '\t'.join(['{%s}'%key for key in self._fields])
        line = boilerplate.format(**vals)
        self._f.write(line)

    def close(self):
        self._f.close()

    def __del__(self):
        self.close()
