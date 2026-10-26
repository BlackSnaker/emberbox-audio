import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_demux import samples


def box(kind,data):return struct.pack('>I4s',len(data)+8,kind)+data

def full(flags):return struct.pack('>I',flags)

def fixture(offset,description=1,override=None,codec=b'ec-3',extra=b'',timescale=None,version=0):
    tenc=box(b'tenc',full(1<<24)+bytes((0,0,1,0))+bytes(16)+bytes((16,))+bytes(range(16)))
    entry=box(b'enca',bytes(28)+extra+box(b'sinf',box(b'frma',codec)+box(b'schm',full(0)+b'cbcs'+bytes(4))+box(b'schi',tenc)))
    second=entry.replace(bytes(range(16)),bytes(reversed(range(16))))
    stsd=box(b'stsd',full(0)+struct.pack('>I',2)+entry+second)
    mdhd=box(b'mdhd',full(version<<24)+bytes(8 if version==0 else 16)+struct.pack('>I',timescale)) if timescale is not None else b''
    trak=box(b'trak',box(b'mdia',mdhd+box(b'minf',box(b'stbl',stsd))))
    trex=box(b'trex',full(0)+struct.pack('>IIIII',1,description,1536,32,0))
    init=box(b'ftyp',b'isom'+bytes(4))+box(b'moov',trak+box(b'mvex',trex))
    def moof(data_offset):
        tfhd=box(b'tfhd',full(1|(2 if override else 0))+struct.pack('>IQ',1,offset)+(struct.pack('>I',override) if override else b''))
        trun=box(b'trun',full(1)+struct.pack('>Ii',2,data_offset))
        senc=box(b'senc',full(2)+struct.pack('>I',2)+2*struct.pack('>HHI',1,16,16))
        return box(b'moof',box(b'mfhd',full(0)+struct.pack('>I',7))+box(b'traf',tfhd+trun+senc))
    header=moof(0);header=moof(len(header)+8)
    data=init+header+box(b'mdat',b'a'*32+b'b'*32)
    return data,len(init)

class DemuxTests(unittest.TestCase):
    def test_seek_sample_durations_keep_the_declared_media_timescale(self):
        for version in (0,1):
            data,init=fixture(0,timescale=48000,version=version)
            values=list(samples(data,init,0))
            self.assertEqual(values[0][1]['timescale'],48000);self.assertEqual(values[0][1]['duration'],1536)
        data,init=fixture(0,timescale=0)
        with self.assertRaises(ValueError):list(samples(data,init,0))

    def test_midtrack_ranges_keep_sample_locations_and_encryption(self):
        for offset in (0,17300342):
            data,init=fixture(offset);values=list(samples(data,init,offset))
            self.assertEqual([p for p,c in values],[b'a'*32,b'b'*32])
            self.assertEqual(values[0][1]['pairs'],[(16,16)])
            self.assertEqual(values[0][1]['iv'],bytes(range(16)))
            self.assertEqual(values[0][1]['scheme'],2)
    def test_selects_the_declared_description_instead_of_merging_encryption_entries(self):
        # Apple initialization contains several encrypted sample descriptions.
        for description,override in ((2,None),(1,2)):
            data,init=fixture(900000,description,override)
            values=list(samples(data,init,900000))
            self.assertEqual(values[0][1]['iv'],bytes(reversed(range(16))))
        data,init=fixture(0,3)
        with self.assertRaises(ValueError):list(samples(data,init,0))
    def test_aac_configuration_is_bound_to_the_selected_encrypted_entry(self):
        def desc(tag,payload):return bytes((tag,len(payload)))+payload
        esds=box(b'esds',full(0)+desc(3,b'\0\1\0'+desc(4,b'\x40\x15'+bytes(11)+desc(5,b'\x12\x10'))))
        data,init=fixture(11000,codec=b'mp4a',extra=esds)
        values=list(samples(data,init,11000))
        self.assertEqual(values[0][1]['codec'],'aac');self.assertEqual(values[0][1]['asc'],b'\x12\x10')
    def test_rejects_truncated_and_out_of_range_samples(self):
        data,init=fixture(1234)
        with self.assertRaises(ValueError):list(samples(data[:-2],init,1234))
        corrupted=bytearray(data);at=corrupted.index(b'trun')+12
        corrupted[at:at+4]=struct.pack('>i',0x7fffffff)
        with self.assertRaises(ValueError):list(samples(corrupted,init,1234))
    def test_missing_drm_metadata_cannot_be_accepted_as_clear_audio(self):
        data,init=fixture(0)
        data=data.replace(b'tenc',b'free')
        with self.assertRaises(ValueError):list(samples(data,init,0))

if __name__=='__main__':unittest.main()
