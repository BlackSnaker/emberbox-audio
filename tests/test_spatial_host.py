"""Native host reuse is independent of song decoding and private profiles."""
import hashlib,queue,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import spatial_worker as worker
from spatial_seek import Seeks
from spatial_fairplay import FairPlay

class SpatialHostTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):worker.control.close()

    def test_idle_host_loads_two_tracks_and_seeks_without_reinitializing_signin(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=Path(tmp)/'fixture';lib.write_bytes(b'fixture');sha=hashlib.sha256(b'fixture').hexdigest()
            runtime={'host':str(lib),'hostSha256':sha,'decoder':str(lib),'decoderSha256':sha,'fairplay':{}}
            def selection(ident):return {'prepared':{'metadata':{'catalogId':ident},'contextId':'context-'+ident,'drm':'fairplay','licences':[{'uri':'skd://itunes.apple.com/P000000000/s1/e1'},{'uri':'skd://itunes.apple.com/P'+ident+'/s1/e1'}]}}
            first,second=selection('123'),selection('456')
            host=Mock(contexts={})
            def license(ident,uri):
                key=('0' if '/P000000000/' in uri else ident,uri);host.contexts[key]='opaque';return 'opaque'
            host.license.side_effect=license
            requests=Mock();requests.next_selection.side_effect=[(0,1,first,threading.Event()),(40,2,None,threading.Event()),(0,3,second,threading.Event()),None]
            bootstrap=queue.Queue();bootstrap.put({'type':'warm','backend':'fairplay','runtime':runtime,'outputRate':48000})
            seen=[]
            def decode(args,prepared,runtime,rate,actual,licensed,authorize,writer,position,generation,cancelled):
                self.assertIs(actual,host);seen.append((prepared['contextId'],position,generation))
                self.assertNotIn(0,licensed,'Unused initialization keys delay the selected track')
                authorize(1);self.assertEqual(set(licensed),{1})
            with patch.object(worker,'bootstrap',bootstrap),patch.object(worker,'seeks',requests),patch.object(worker,'listen'),patch.object(worker,'FairPlay',return_value=host) as construct,patch.object(worker,'PcmWriter'),patch.object(worker,'decode_pass',side_effect=decode),patch.object(worker,'emit'),patch('spatial_worker.os.dup2'),patch('spatial_worker.os.close'):
                worker.main()
            construct.assert_called_once_with({});host.close.assert_called_once()
            self.assertEqual(seen,[('context-123',0,1),('context-123',40,2),('context-456',0,3)])
            self.assertEqual(len(host.contexts),2)
            self.assertTrue(all('/P000000000/' not in call.args[1] for call in host.license.call_args_list))

    def test_shared_initialization_license_does_not_consume_a_context_for_each_song(self):
        host=FairPlay.__new__(FairPlay);host.contexts={};host.open_fn=Mock(return_value=123)
        shared='skd://itunes.apple.com/P000000000/s1/e1'
        self.assertEqual(host.license('123',shared),host.license('456',shared))
        host.open_fn.assert_called_once();self.assertEqual(host.open_fn.call_args.args[0],b'0')
        host.license('123','skd://itunes.apple.com/P123/s1/e1');host.license('456','skd://itunes.apple.com/P456/s1/e1')
        self.assertEqual(len(host.contexts),3)

    def test_park_cancels_old_decode_and_next_load_owns_its_descriptor(self):
        requests=Seeks();requests.submit(0,1,{'prepared':'old'})
        _,_,selection,cancelled=requests.next_selection();self.assertEqual(selection['prepared'],'old')
        requests.park();self.assertTrue(cancelled.is_set())
        requests.submit(30,2,{'prepared':'superseded'});requests.submit(0,3,{'prepared':'new'})
        position,generation,selection,cancelled=requests.next_selection()
        self.assertEqual((position,generation,selection),(0,3,{'prepared':'new'}));self.assertFalse(cancelled.is_set());requests.close()

if __name__=='__main__':unittest.main()
