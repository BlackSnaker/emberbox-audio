"""Execute the Spotify artist readers against music-only offline DOM fixtures."""
import json
from pathlib import Path
import subprocess,sys,unittest
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spotify_artist import REFERENCES,CHOICES,NAVIGATE,SpotifyArtist


class SpotifyArtists(unittest.TestCase):
    def test_exact_track_identity_guards_a_late_current_artist(self):
        harness=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const {refs,choices}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let track='ABC';
const artist={textContent:'Artist',getAttribute:()=>'/artist/ART',closest:()=>null};
const footer={querySelector:()=>({getAttribute:()=>'/track/'+track}),querySelectorAll:()=>[artist]};
const document={querySelector:()=>footer,querySelectorAll:()=>[]};
Object.defineProperty(document,'cookie',{get(){throw Error('Never read credentials');}});
const context={document};
assert.equal(vm.runInNewContext(refs,context)[0].id,'ART');
track='NEW';assert.equal(vm.runInNewContext(refs,context).length,0,'A late request must not select the next song artist');
assert.equal(vm.runInNewContext(choices,context).length,0);
'''
        script=REFERENCES.replace('URI',json.dumps('spotify:track:ABC')).replace('CURRENT','true')
        result=subprocess.run(['node','-e',harness],input=json.dumps({'refs':script,'choices':CHOICES}),capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_navigation_rejects_non_music_paths_before_evaluation(self):
        client=MagicMock();adapter=SpotifyArtist(client)
        for path in ('/account','https://example.invalid/artist/A','/artist/../account','/album/A?token=secret'):
            with self.assertRaises(ValueError):adapter.navigate(path)
        client.evaluate.assert_not_called()
        client.evaluate.return_value=False
        with self.assertRaises(RuntimeError):adapter.navigate('/artist/ABC')
        self.assertNotIn('location.href',NAVIGATE,'Browsing must not force a playback-stopping page reload')


if __name__=='__main__':unittest.main()
