import ctypes as C
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_fairplay import FairPlay


class FairPlayPacketTests(unittest.TestCase):
    def test_preserves_clear_bytes_and_partial_blocks(self):
        decoder=FairPlay.__new__(FairPlay);calls=[]
        def decrypt(handle,epoch,pointer,length):
            calls.append((handle,epoch,length))
            data=(C.c_ubyte*length).from_address(C.cast(pointer,C.c_void_p).value)
            for i in range(length):data[i]^=255
            return 0
        decoder.decrypt_fn=decrypt
        packet=bytes(range(60));out=[]
        crypto={'scheme':2,'skip':0,'iv_size':0,'pairs':[(4,20),(4,32)]}
        decoder.decode_sample(packet,crypto,(123,7),lambda p,n:out.append(C.string_at(p,n)))
        expected=bytearray(packet)
        for start,end in ((4,20),(28,60)):
            for i in range(start,end):expected[i]^=255
        self.assertEqual(out,[bytes(expected)]);self.assertEqual(calls,[(123,7,16),(123,7,32)])

    def test_unsupported_encryption_never_reaches_native_memory(self):
        decoder=FairPlay.__new__(FairPlay)
        decoder.decrypt_fn=lambda *_:self.fail('Unsafe packet reached native decryptor')
        valid={'scheme':2,'skip':0,'iv_size':0,'pairs':[]}
        for crypto in ({**valid,'scheme':1},{**valid,'skip':9},{**valid,'iv_size':16},
                       {**valid,'pairs':[(1,100)]},{**valid,'pairs':[(-1,33)]}):
            with self.assertRaises(ValueError):decoder.decode_sample(bytes(32),crypto,(1,0),lambda *_:None)

    def test_license_identifiers_cannot_be_arbitrary_urls(self):
        decoder=FairPlay.__new__(FairPlay);decoder.contexts={}
        for ident,uri in (('x','skd://itunes.apple.com/P1/s1/e1'),('1','https://example.com/key'),
                          ('1','skd://itunes.apple.com/P1?token=private')):
            with self.assertRaises(ValueError):decoder.license(ident,uri)


if __name__=='__main__':unittest.main()
