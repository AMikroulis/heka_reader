"""
Heka Patchmaster .dat file reader 

Structure definitions adapted from StimFit hekalib.cpp
"""


import numpy as np
import struct, collections


#level = {
    #'root': 0,
    #'group': 1,
    #'series': 2,
    #'sweep': 3,
    #'trace': 4
#}
#levels = ['root', 'group', 'series', 'sweep', 'trace']

#tree_entry = 'iii', ('level', 'counter', 'idx')
#bundle_item = 'ii8s', ('start', 'length', 'ext')
#assert struct.calcsize(bundle_item[0]) == 16

#bundle_header = '8s32sdi12s', (
    #'signature', 
    #'version', 
    #'time', 
    #'items', 
    #'endian', 
#)
#assert struct.calcsize(bundle_header[0]) == 64

#trace_record = 'i32siiiiiiihhccccddd8sdd8sdddddddddddicchddiidddiidii', (
    #'mark',
    #'label',
    #'trace_count',
    #'data',
    #'data_points',
    #'internal_solution',
    #'average_count',
    #'leak_count',
    #'leak_traces',
    #'data_kind',
    #'filler1',
    #'recording_mode',
    #'ampl_index',
    #'data_format',
    #'data_abscissa',
    #'data_scaler',
    #'time_offset',
    #'zero_data',
    #'y_unit',
    #'x_interval',
    #'x_start',
    #'x_unit',
    #'y_range',
    #'y_offset',
    #'bandwidth',
    #'pipette_resistance',
    #'cell_potential',
    #'seal_resistance',
    #'c_slow',
    #'g_series',
    #'rs_value',
    #'g_leak',
    #'m_conductance',
    #'link_da_channel',
    #'valid_y_range',
    #'adc_mode',
    #'adc_channel',
    #'y_min',
    #'y_max',
    #'source_channel',
    #'external_solution',
    #'cm',
    #'gm',
    #'phase',
    #'data_crc',
    #'crc',
    #'gs',
    #'self_channel',
    #'filler2',    
#)
#assert struct.calcsize(trace_record[0]) == 296


#sweep_record = 'i32siiidd4ddiihhi4dii', (
    #'mark',
    #'label',
    #'aux_data_file_offset',
    #'stim_count',
    #'sweep_count',
    #'time',
    #'timer',
    #'sw_user_params[0]',
    #'sw_user_params[1]',
    #'sw_user_params[2]',
    #'sw_user_params[3]',
    #'temperature',
    #'old_int_sol',
    #'old_ext_sol',
    #'digital_in',
    #'sweep_kind',
    #'filler1',
    #'markers[0]',
    #'markers[1]',
    #'markers[2]',
    #'markers[3]',
    #'filler2',
    #'crc'
#)
#assert struct.calcsize(sweep_record[0]) == 160

#user_param_descr = '32s8s', ('name', 'unit')


#amplifier_state = '8s24d8s12h32c2d16c2d4h24s16sd32s', (
    #'',
#)
#assert struct.calcsize(amplifier_state[0]) == 400

class Struct(object):
    """Convenience class that makes it a bit easier to unpack large structures.
    
    * Unpacks to dictionary allowing fields to be retrieved by name
    * Optionally massages field data on read
    * Handles arrays and nested structures
    
    *fields* must be a list of tuples like (name, format) or (name, format, function)
    where *format* must be a simple struct format string like 'i', 'd', 
    '32s', or '4d'; or another Struct instance.
    
    *function* may be either a function that filters the data for that field
    or None to exclude the field altogether.
    
    If *size* is given, then an exception will be raised if the final struct size
    does not match the given size.

    
    Example::
        
        Struct([
            ('char_field', 'c'),          # single char 
            ('char_array', '8c'),         # list of 8 chars
            ('str_field',  '8s', cstr),   # string of len 8, passed through cstr()
            ('sub_struct', s2),           # dict generated by s2.unpack 
            ('struct_array', 8*s2),       # list of 8 dicts
            ('filler', '32s', None),      # ignored field
        ], size=300)
    
    """
    def __init__(self, fields, size=None):
        fmt = ''
        self.fields = []
        for items in fields:
            if len(items) == 3:
                name, ifmt, func = items
            else:
                name, ifmt = items
                func = True
                
            if isinstance(ifmt, Struct):
                func = (ifmt, func) # instructs to unpack with sub-struct before calling function
                typ = '%ds' % ifmt.size
            elif len(ifmt) > 1 and re.match(r'\d*[xcbB?hHiIlLqQfdspP]', ifmt) is None:
                raise TypeError('Unsupported format string "%s"' % ifmt)
            
            self.fields = (name, ifmt, func)
            fmt += typ
        self.le = struct.Struct('<' + fmt)
        self.be = struct.Struct('>' + fmt)
        if size is not None:
            assert self.le.size == size

    @propertry
    def size(self):
        return self.le.size
        
    def unpack(self, data, endian='<'):
        """Read the structure from *data* and return an ordered dictionary of 
        fields.
        
        *data* may be a string or file.
        *endian* may be '<' or '>'
        """
        if not isinstance(data, (str, bytes)):
            data = data.read(self.le.size)
        if endian == '<':
            items = self.le.unpack(data)
        elif endian == '>':
            items = self.be.unpack(data)
        else:
            raise ValueError('Invalid endian: %s' % endian)
        
        assert len(items) == len(self.fields)
        fields = collections.OrderedDict()
        
        i = 0
        while len(items) > 0:
            name, fmt, func = self.fields[i]
            
            # pull item(s) out of the list based on format string
            if len(fmt) == 0 or fmt[-1] == 's':
                item = items[i]
                i += 1
            else:
                n = int(fmt[:-1])
                item = items[i:i+n]
                i += n
            
            # try unpacking sub-structure
            if isinstance(func, tuple):
                substr, func = func
                item = substr.unpack(item, endian)
                i += 1
            
            # None here means the field should be omitted
            if func is None:
                continue
            # handle custom massaging function
            if func is not True:
                item = func(item)
            fields[name] = item
            
        return fields
    
    def __mul__(self, x):
        return StructArray(self, x)

    
class StructArray(Struct):
    def __init__(self, item_struct, x):
        self.item_struct = item_struct
        self.x = x
        
    @property
    def size(self):
        return self.item_struct.size * self.x
    
    def unpack(self, data, endian='<'):
        if not isinstance(data, (str, bytes)):
            data = data.read(self.size)
        out = []
        isize = self.item_struct.size
        for i in range(self.x):
            d = data[:isize]
            data = data[isize:]
            out.append(self.item_struct.unpack(d, endian))
        return out


def cstr(byt):
    """Convert C string bytes to python string.
    """
    try:
        ind = byt.index(b'\0')
    except ValueError:
        return byt
    return byt[:ind].decode('utf-8', errors='ignore')


bundle_item = Struct([
   ('Start', 'i'),
   ('Length', 'i'),
   ('Extension', '8s'),
], size=16)


bundle_header = Struct([
    ('Signature', '8s', cstr),
    ('Version', '32s', cstr),
    ('Time', 'd'),
    ('Items', 'i'),
    ('IsLittleEndian', '12s'),
    ('BundleItems', 12*bundle_item),
], size=256)


trace_record = Struct([
    ('Mark', 'i'),
    ('Label', '32s'),
    ('TraceCount', 'i'),
    ('Data', 'i'),
    ('DataPoints', 'i'),
    ('InternalSolution', 'i'),
    ('AverageCount', 'i'),
    ('LeakCount', 'i'),
    ('LeakTraces', 'i'),
    ('DataKind', 'h'),
    ('Filler1', 'h'),
    ('RecordingMode', 'c'),
    ('AmplIndex', 'c'),
    ('DataFormat', 'c'),
    ('DataAbscissa', 'c'),
    ('DataScaler', 'd'),
    ('TimeOffset', 'd'),
    ('ZeroData', 'd'),
    ('YUnit', '8s'),
    ('XInterval', 'd'),
    ('XStart', 'd'),
    ('XUnit', '8s'),
    ('YRange', 'd'),
    ('YOffset', 'd'),
    ('Bandwidth', 'd'),
    ('PipetteResistance', 'd'),
    ('CellPotential', 'd'),
    ('SealResistance', 'd'),
    ('CSlow', 'd'),
    ('GSeries', 'd'),
    ('RsValue', 'd'),
    ('GLeak', 'd'),
    ('MConductance', 'd'),
    ('LinkDAChannel', 'i'),
    ('ValidYrange', 'c'),
    ('AdcMode', 'c'),
    ('AdcChannel', 'h'),
    ('Ymin', 'd'),
    ('Ymax', 'd'),
    ('SourceChannel', 'i'),
    ('ExternalSolution', 'i'),
    ('CM', 'd'),
    ('GM', 'd'),
    ('Phase', 'd'),
    ('DataCRC', 'i'),
    ('CRC', 'i'),
    ('GS', 'd'),
    ('SelfChannel', 'i'),
    ('Filler2', 'i'),
], size=296)


sweep_record = Struct([
    ('Mark', 'i'),
    ('Label', '32s'),
    ('AuxDataFileOffset', 'i'),
    ('StimCount', 'i'),
    ('SweepCount', 'i'),
    ('Time', 'd'),
    ('Timer', 'd'),
    ('SwUserParams', '4d'),
    ('Temperature', 'd'),
    ('OldIntSol', 'i'),
    ('OldExtSol', 'i'),
    ('DigitalIn', 'h'),
    ('SweepKind', 'h'),
    ('Filler1', 'i'),
    ('Markers', '4d'),
    ('Filler2', 'i'),
    ('CRC', 'i'),
], size=160)


user_param_descr_type = Struct[
    ('Name', '32s'),
    ('Unit', '8s'),
], size=40)


amplifier_state = Struct([
    ('StateVersion', '8s', cstr),
    ('RealCurrentGain', 'd'),
    ('RealF2Bandwidth', 'd'),
    ('F2Frequency', 'd'),
    ('RsValue', 'd'),
    ('RsFraction', 'd'),
    ('GLeak', 'd'),
    ('CFastAmp1', 'd'),
    ('CFastAmp2', 'd'),
    ('CFastTau', 'd'),
    ('CSlow', 'd'),
    ('GSeries', 'd'),
    ('StimDacScale', 'd'),
    ('CCStimScale', 'd'),
    ('VHold', 'd'),
    ('LastVHold', 'd'),
    ('VpOffset', 'd'),
    ('VLiquidJunction', 'd'),
    ('CCIHold', 'd'),
    ('CSlowStimVolts', 'd'),
    ('CCTrackVHold', 'd'),
    ('TimeoutLength', 'd'),
    ('SearchDelay', 'd'),
    ('MConductance', 'd'),
    ('MCapacitance', 'd'),
    ('SerialNumber', '8s', cstr),
    ('E9Boards', 'h'),
    ('CSlowCycles', 'h'),
    ('IMonAdc', 'h'),
    ('VMonAdc', 'h'),
    ('MuxAdc', 'h'),
    ('TstDac', 'h'),
    ('StimDac', 'h'),
    ('StimDacOffset', 'h'),
    ('MaxDigitalBit', 'h'),
    ('SpareInt1', 'h'),
    ('SpareInt2', 'h'),
    ('SpareInt3', 'h'),

    ('AmplKind', 'c'),
    ('IsEpc9N', 'c'),
    ('ADBoard', 'c'),
    ('BoardVersion', 'c'),
    ('ActiveE9Board', 'c'),
    ('Mode', 'c'),
    ('Range', 'c'),
    ('F2Response', 'c'),

    ('RsOn', 'c'),
    ('CSlowRange', 'c'),
    ('CCRange', 'c'),
    ('CCGain', 'c'),
    ('CSlowToTstDac', 'c'),
    ('StimPath', 'c'),
    ('CCTrackTau', 'c'),
    ('WasClipping', 'c'),

    ('RepetitiveCSlow', 'c'),
    ('LastCSlowRange', 'c'),
    ('Locked', 'c'),
    ('CanCCFast', 'c'),
    ('CanLowCCRange', 'c'),
    ('CanHighCCRange', 'c'),
    ('CanCCTracking', 'c'),
    ('HasVmonPath', 'c'),

    ('HasNewCCMode', 'c'),
    ('Selector', 'c'),
    ('HoldInverted', 'c'),
    ('AutoCFast', 'c'),
    ('AutoCSlow', 'c'),
    ('HasVmonX100', 'c'),
    ('TestDacOn', 'c'),
    ('QMuxAdcOn', 'c'),

    ('RealImon1Bandwidth', 'd'),
    ('StimScale', 'd'),

    ('Gain', 'c'),
    ('Filter1', 'c'),
    ('StimFilterOn', 'c'),
    ('RsSlow', 'c'),
    ('Old1', 'c'),
    ('CCCFastOn', 'c'),
    ('CCFastSpeed', 'c'),
    ('F2Source', 'c'),

    ('TestRange', 'c'),
    ('TestDacPath', 'c'),
    ('MuxChannel', 'c'),
    ('MuxGain64', 'c'),
    ('VmonX100', 'c'),
    ('IsQuadro', 'c'),
    ('SpareBool4', 'c'),
    ('SpareBool5', 'c'),

    ('StimFilterHz', 'd'),
    ('RsTau', 'd'),
    ('FilterOffsetDac', 'h'),
    ('ReferenceDac', 'h'),
    ('SpareInt6', 'h'),
    ('SpareInt7', 'h'),
    ('Spares1', '24s'),
    
    ('CalibDate', '16s'),
    ('SelHold', 'd'),
    ('Spares2', '32s'),
], size=400)
    
    
lockin_params = Struct([
    ('ExtCalPhase', 'd'),
    ('ExtCalAtten', 'd'),
    ('PLPhase', 'd'),
    ('PLPhaseY1', 'd'),
    ('PLPhaseY2', 'd'),
    ('UsedPhaseShift', 'd'),
    ('UsedAttenuation', 'd'),
    ('Spares2', '8s'),
    ('ExtCalValid', '?'),
    ('PLPhaseValid', '?'),
    ('LockInMode', 'c'),
    ('CalMode', 'c'),
    ('Spares', '28s'),
], size=96)


#series_record = 'i32s80siiiiccccdd160s32s4d96s400s80s160sii', (
    #'mark',
    #'label',
    #'comment',
    #'series_count',
    #'number_sweeps',
    #'ampl_state_offset',
    #'ampl_state_series',
    #'series_type',
    #'filler1',
    #'filler2',
    #'filler3',
    #'time',
    #'page_width',
    #'sw_user_param_descr',
    #'filler4',
    #'se_user_params[0]',
    #'se_user_params[1]',
    #'se_user_params[2]',
    #'se_user_params[3]',
    #'se_lock_in_params',
    #'se_amplifier_state',
    #'username',
    #'se_user_param_descr',
    #'filler5',
    #'crc'
#)
#assert struct.calcsize(series_record[0]) == 1120

series_record = Struct([
    ('SeMark', 'i'),
    ('SeLabel', '32s'),
    ('SeComment', '80s'),
    ('SeSeriesCount', 'i'),
    ('SeNumberSweeps', 'i'),
    ('SeAmplStateOffset', 'i'),
    ('SeAmplStateSeries', 'i'),
    ('SeriesType', 'c'),
    ('Filler1', 'c'),
    ('Filler2', 'c'),
    ('Filler3', 'c'),
    ('Time', 'd'),
    ('PageWidth', 'd'),
    ('SwUserParamDescr', 4*user_param_descr_type),
    ('SeFiller4', '32s'),
    ('SeSeUserParams[4]', 'd'),
    ('LockInParams', lockin_params),
    ('AmplifierState', amplifier_state),
    ('SeUsername', '80s'),
    ('SeUserParamDescr', 4*user_param_descr_type),
    ('SeFiller5', 'i'),
    ('SeCRC', 'i'),
    ], size=1120};

group_record = Struct([
    ('GrMark', 'i'),
    ('GrLabel', '32s'),
    ('GrText', '80s'),
    ('GrExperimentNumber', 'i'),
    ('GrGroupCount', 'i'),
    ('GrCRC', 'i'),
], size=128)


root_record = Struct([
    ('RoVersion', 'i'),
    ('RoMark', 'i'),
    ('RoVersionName', '32s'),
    ('RoAuxFileName', '80s'),
    ('RoRootText', '400s'),
    ('RoStartTime', 'd'),
    ('RoMaxSamples', 'i'),
    ('RoCRC', 'i'),
    ('RoFeatures', 'h'),
    ('RoFiller1', 'h'),
    ('RoFiller2', 'i'),
], size=544)


#group_record = 'i32s80siii', (
    #'mark',
    #'label',
    #'text',
    #'experiment_number',
    #'group_count',
    #'crc'
#)
#assert struct.calcsize(group_record[0]) == 128


#root_record = 'ii32s80s400sdiihhi', (
    #'version',
    #'mark',
    #'version_name',
    #'aux_file_name',
    #'root_text',
    #'start_time',
    #'max_samples',
    #'crc',
    #'features',
    #'filler1',
    #'filler2'
#)
#assert struct.calcsize(root_record[0]) == 544


    

#def apply_struct(fields, obj):
    #"""Turn all values from a *fields* dictionary (output of Struct.unpack)
    #into attributes of *obj*.
    
    #Also converts some string field types 
    #"""
        #str_fields = ['ext', 'version_name', 'root_text', 'aux_file_name',
                      #'text', 'label', 'comment', 'username', 'x_unit', 'y_unit', 
                      #'se_user_param_descr', 'sw_user_param_descr']
        
        #for i, item in enumerate(items):
            #name = self.field_formats[i][0]
            #if name.startswith('filler'):
                #continue
            #if isinstance(item, bytes) and name in str_fields:
                #item = cstr(item)
            #self._fields[name] = item


class StructInst(object):
    """Abstrict class that converts a dictionary of struct fields to attributes
    on this object.
    """
    def __init__(self, data, struct, endian):
        fields = struct.unpack(data, endian)
        self._fields = fields
        self.__dict__.update(fields)

    def __repr__(self):
        return '%s(\n' + '\n'.join(['    %s = %r' for name,val in self._fields.items()]) + '\n)'
        
        


class TreeNode(StructInst):
    
    # read tree recursively
    rectypes = [
        root_record,
        group_record,
        series_record,
        sweep_record,
        trace_record
    ]
    
    level_names = ['Root', 'Group', 'Series', 'Sweep', 'Trace']

    def __init__(self, fh, pul, level=0):
        self.level = level
        endian = pul.endian
        rectype = self.rectypes[level]
        
        # The record structure in the file may differ from our expected structure
        # due to version differences, so we read the required number of bytes, and
        # then pad or truncate before unpacking the record. This will probably
        # result in corrupt data in some situations..
        realsize = pul.level_sizes[level]
        structsize = struct.calcsize(rectype[0])
        data = fh.read(realsize)
        diff = structsize - realsize
        if diff > 0:
            data = data + b'\0'*diff
        else:
            data = data[:structsize]
        
        # Read structure and assign attributes to self
        StructInst.__init__(self, data, rectype, endian)
        
        # Next read the number of children
        nchild = struct.unpack(endian + 'i', fh.read(4))[0]
            
        self.children = []
        for i in range(nchild):
            self.children.append(TreeNode(fh, pul, level+1))

    def __getitem__(self, i):
        return self.children[i]
    
    def __len__(self):
        return len(self.children)
    
    def __iter__(self):
        return self.children.__iter__()
    
    def __repr__(self):
        # Return a string describing this structure
        fields = ["    %s = %r" % (n, i) for n, i in self._fields.items()]
        return '%s( children=%d\n' % (self.level_names[self.level], len(self)) + '\n'.join(fields) + '\n)'


class Pulsed(TreeNode):
    def __init__(self, bundle, offset=0, size=None):
        fh = open(bundle.file_name, 'rb')
        fh.seek(offset)
        
        # read .pul header
        magic = fh.read(4) 
        if magic == b'eerT':
            self.endian = '<'
        elif magic == b'Tree':
            self.endian = '>'
        else:
            raise RuntimeError('Bad file magic: %s' % magic)
        
        levels = struct.unpack(self.endian + 'i', fh.read(4))[0]

        # read size of each level (one int per level)
        self.level_sizes = []
        for i in range(levels):
            size = struct.unpack(self.endian + 'i', fh.read(4))[0]
            self.level_sizes.append(size)
            
        TreeNode.__init__(self, fh, self)


class Data(object):
    def __init__(self, bundle, offset=0, size=None):
        self.bundle = bundle
        self.offset = offset
        
    def __getitem__(self, *args):
        index = args[0]
        assert len(index) == 4
        pul = self.bundle.pul
        trace = pul[index[0]][index[1]][index[2]][index[3]]
        fh = open(self.bundle.file_name, 'rb')
        fh.seek(trace.data)
        fmt = bytearray(trace.data_format)[0]
        dtype = [np.int16, np.int32, np.float16, np.float32][fmt]
        data = np.fromfile(fh, count=trace.data_points, dtype=dtype)
        return data * trace.data_scaler + trace.zero_data


class Bundle(object):
    
    item_classes = {
        '.pul': Pulsed,
        '.dat': Data,
    }
    
    def __init__(self, file_name):
        self.file_name = file_name
        fh = open(file_name, 'rb')
        
        # Read header assuming little endiam
        endian = '<'
        self.header = bundle_header.unpack(data)

        # If the header is bad, re-read using big endian
        if self.header.endian[0] == b'\0':
            endian = '>'
            self.header = Struct(fh, endian + bundle_header[0], bundle_header[1])
            
        # Read bundle items
        self.bundle_items = [Struct(fh, endian + bundle_item[0], bundle_item[1]) for i in range(12)]

        # catalog extensions of bundled items
        self.catalog = {}
        for item in self.bundle_items:
            item.instance = None
            ext = item.ext
            self.catalog[ext] = item
            
        fh.close()

    @property
    def pul(self):
        """The Pulsed object from this bundle.
        """
        return self._get_item_instance('.pul')
    
    @property
    def data(self):
        """The Data object from this bundle.
        """
        return self._get_item_instance('.dat')
        
    def _get_item_instance(self, ext):
        if ext not in self.catalog:
            return None
        item = self.catalog[ext]
        if item.instance is None:
            cls = self.item_classes[ext]
            item.instance = cls(self, item.start, item.length)
        return item.instance
        
    def __repr__(self):
        return "Bundle(%r)" % list(self.catalog.keys())



if __name__ == '__main__':
    import pyqtgraph as pg
    b = Bundle('DemoV9Bundle.dat')
    trace = b.pul[0][0][0][0]
    plt = pg.plot(labels={'bottom': ('Time', 's'), 'left': (trace.label, trace.y_unit)})
    for i in range(len(b.pul[0][0][0])):
        plt.plot(b.data[0, 0, 0, i])
