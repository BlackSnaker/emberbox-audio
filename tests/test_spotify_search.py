"""Execute the actual Spotify search scripts against an isolated music DOM."""
import json
from pathlib import Path
import subprocess,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from discovery import LocalSpotify


class SpotifySearch(unittest.TestCase):
    def test_scripts_read_music_only_and_keep_query_literal(self):
        client=LocalSpotify();scripts=[]
        def evaluate(script):
            scripts.append(script)
            return True if len(scripts)<3 else {'items':[{'uri':'spotify:track:ABC'}]}
        client.evaluate=evaluate
        query="evening '); globalThis.injected = true; //"
        with patch('discovery.time.sleep'):
            client.search(query)
        harness=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const {scripts,query}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Input{set value(v){this._value=v;}get value(){return this._value;}dispatchEvent(e){this.events.push(e.type);}}
const input=new Input();input.events=[];
const card={querySelector:s=>s.includes('cardTitle')?{textContent:'Album'}:s.includes('cardSubtitle')?{textContent:'Artist'}:{src:'https://example.invalid/album.jpg'}};
const album={getAttribute:()=>'/album/ALB',closest:()=>card};
const row={privateToken:'NEVER_EXPORT',querySelector:s=>s.includes('/track/')?{getAttribute:()=>'/track/ABC',textContent:'Amber'}:
  s.includes('/album/')?{textContent:'Album'}:{src:'https://example.invalid/track.jpg'},
  querySelectorAll:s=>s.includes('/artist/')?[{textContent:'Artist'}]:[{textContent:'3:30'}]};
const document={querySelector:()=>input,querySelectorAll:s=>s.includes('tracklist-row')?[row]:[album]};
Object.defineProperty(document,'cookie',{get(){throw Error('Credentials must not be read');}});
const context={document,HTMLInputElement:Input,Event:class{constructor(type){this.type=type;}},Set};
assert.equal(vm.runInNewContext(scripts[0],context),true);
assert.equal(vm.runInNewContext(scripts[1],context),true);
assert.equal(input.value,query);assert.equal(context.injected,undefined);
const result=vm.runInNewContext(scripts[2],context);
assert.equal(result.items[0].uri,'spotify:track:ABC');assert.equal(result.items[0].duration_ms,210000);
assert.equal(result.items[1].uri,'spotify:album:ALB');assert.equal(result.items[1].kind,'album');
assert(!JSON.stringify(result).includes('NEVER_EXPORT'));
'''
        result=subprocess.run(['node','-e',harness],input=json.dumps({'scripts':scripts,'query':query}),
                              capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
