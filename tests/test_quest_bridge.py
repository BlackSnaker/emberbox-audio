"""Loopback pairing, command dispatch and private metadata boundaries; no audio."""
import os,sys,tempfile,threading,unittest,json
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import GLib
from quest_bridge import QuestBridge,public

class BridgeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'index.html').write_text('Ember test')
  self.old=os.environ.get('XDG_RUNTIME_DIR');os.environ['XDG_RUNTIME_DIR']=self.temp.name
  label=lambda value:NS(get_text=lambda:value)
  self.calls=[]
  self.host=NS(source='youtube',youtube_mode='native',youtube=NS(current={'id':'demo'},eof=False),title=label('Original fixture'),artist=label('Ember Sessions'),album=label('Fixture'),playing=True,length=120000000,position=1000000,art_url='',sound=NS(volume=.5,muted=False,set_volume=lambda v:self.calls.append(v)),meter=NS(levels=[.1]*9,rms_level=.1,beat_grid=None),music=NS(book=NS(upcoming=lambda _:[]),flow=NS(enabled=False),favorites=NS(current=lambda:None,saved=lambda _:False)),on_action=lambda _,action:self.calls.append(action))
  self.loop=GLib.MainLoop();self.thread=threading.Thread(target=self.loop.run);self.thread.start()
  self.bridge=QuestBridge(self.host,self.root,port=0);self.base=f'http://127.0.0.1:{self.bridge.port}'
 def tearDown(self):
  self.bridge.close();self.loop.quit();self.thread.join(2)
  if self.old is None:os.environ.pop('XDG_RUNTIME_DIR',None)
  else:os.environ['XDG_RUNTIME_DIR']=self.old
  self.temp.cleanup()
 def req(self,path,data=None,token=True,origin=None):
  headers={'Authorization':'Bearer '+self.bridge.token} if token else {}
  if origin:headers['Origin']=origin
  request=Request(self.base+path,data=json.dumps(data).encode() if data else None,headers=headers)
  return urlopen(request,timeout=3)
 def test_private_state_requires_pair_and_correct_origin(self):
  for args in ({'token':False},{'origin':'https://example.invalid'}):
   with self.assertRaises(HTTPError) as err:self.req('/api/state',**args)
   self.assertEqual(err.exception.code,403);err.exception.close()
  with self.req('/api/state') as reply:state=json.load(reply)
  self.assertEqual(state['title'],'Original fixture');self.assertNotIn('token',state);self.assertIsNone(self.bridge.tap)
  self.assertEqual(self.bridge.pair_file.stat().st_mode&0o777,0o600)
 def test_hosted_app_preflight_is_explicit_and_still_requires_token(self):
  self.bridge.web_origin='https://ember.example'
  request=Request(self.base+'/api/state',headers={'Origin':'https://ember.example'},method='OPTIONS')
  with urlopen(request) as reply:
   self.assertEqual(reply.status,204);self.assertEqual(reply.headers['Access-Control-Allow-Origin'],'https://ember.example')
  with self.req('/api/state',origin='https://ember.example') as reply:self.assertIn('title',json.load(reply))
  with self.assertRaises(HTTPError) as err:self.req('/api/state',token=False,origin='https://ember.example')
  self.assertEqual(err.exception.code,403);err.exception.close()
 def test_non_finite_controls_rejected(self):
  for value in ('NaN','inf','-inf'):
   with self.assertRaises(HTTPError) as err:self.req('/api/action',{'op':'volume','value':value})
   self.assertEqual(err.exception.code,400);err.exception.close()
 def test_transport_dispatch_and_unsupported_command(self):
  with self.req('/api/action',{'op':'next'}) as reply:self.assertTrue(json.load(reply)['ok'])
  self.assertEqual(self.calls,['next'])
  with self.assertRaises(HTTPError):self.req('/api/action',{'op':'execute','value':'untrusted'})
  self.assertEqual(self.calls,['next'])
 def test_static_path_traversal_and_secret_fields(self):
  with self.req('/') as reply:self.assertEqual(reply.read(),b'Ember test')
  with self.assertRaises(HTTPError):self.req('/../../etc/passwd')
  self.assertEqual(public({'title':'Safe','token':'private','cookies':['private'],'items':[{'uri':'demo','password':'private'}]}),{'title':'Safe','items':[{'uri':'demo'}]})
 def test_image_request_cannot_target_loopback(self):
  for uri in ('http://localhost/private','https://localhost/private','file:///private'):
   with self.assertRaises(ValueError):self.bridge.image(uri)

if __name__=='__main__':unittest.main()
