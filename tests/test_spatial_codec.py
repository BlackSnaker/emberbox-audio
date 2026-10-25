import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_codec import key_identifier

class SpatialInitTests(unittest.TestCase):
    def fixture(self,tail=b'\x48\x01\x50\x02'):
        kid=bytes(range(16));payload=b'\x08\x01\x12\x10'+kid+tail
        return (32+len(payload)).to_bytes(4,'big')+b'pssh'+b'\0'*4+bytes.fromhex('edef8ba979d64acea3c827dcd51d21ed')+len(payload).to_bytes(4,'big')+payload,kid
    def test_real_apple_shape_has_trailing_fields_not_part_of_the_key_identifier(self):
        data,kid=self.fixture();self.assertEqual(len(data),56)
        self.assertEqual(key_identifier(data),kid);self.assertNotEqual(data[-16:],kid)
    def test_accepts_the_simple_musickit_init_shape(self):
        data,kid=self.fixture(b'');self.assertEqual(key_identifier(data),kid)
    def test_rejects_truncation_and_malformed_varints(self):
        data,_=self.fixture()
        for malformed in (b'',data[:-1],b'\0'*56,data[:32]+b'\xff'*24):
            with self.assertRaises(ValueError):key_identifier(malformed)
    def test_bounded_init_data(self):
        with self.assertRaises(ValueError):key_identifier(b'\0'*131073)

if __name__=='__main__':unittest.main()
