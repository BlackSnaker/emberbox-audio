"""Karaoke frames keep accurate words without invalidating unchanged layouts."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from karaoke import KaraokeView,LyricScenes,WordHighlight,moment
from karaoke_timeline import HeardTimeline,PlaybackPoint
from lyrics import LyricLine,LyricWord,LyricsState


class Control:
    def __init__(self):
        self.mutations=0;self.value=0;self.text='';self.sensitive=True
    def set_text(self,value):self.text=value;self.mutations+=1
    def get_text(self):return self.text
    def set_attributes(self,value):self.mutations+=1
    def set_sensitive(self,value):self.sensitive=value;self.mutations+=1
    def get_sensitive(self):return self.sensitive
    def set_visible(self,value):self.mutations+=1
    def set_no_show_all(self,value):self.mutations+=1
    def set_visible_child_name(self,value):self.mutations+=1
    def set_range(self,*value):self.mutations+=1
    def set_value(self,value):self.value=value;self.mutations+=1
    def get_value(self):return self.value


def fixture():
    words=(LyricWord(1,2,0,5),LyricWord(2,3,5,10))
    state=LyricsState('ready',(LyricLine(1,'Warm light',words),LyricLine(10,'Stay awhile')))
    labels=[[Control() for _ in range(3)] for _ in range(2)]
    controls={key:Control() for key in ('song','cover','countdown','timing_note','auto_button','import_button')}
    stage_controls={key:Control() for key in ('progress','elapsed','total','playing_caption')}
    timeline=HeardTimeline()
    timeline.observe(PlaybackPoint(0,('same',),'Fixture','Artist',2.5,180,False,'same'),state)
    stage=SimpleNamespace(lyrics=SimpleNamespace(state=state,key=('same',)),
        host=SimpleNamespace(progress_event=Control()),artwork=SimpleNamespace(load=lambda *a,**kw:None),**stage_controls)
    view=SimpleNamespace(stage=stage,audio=SimpleNamespace(active=True,engine='ai',delay=1.8),
        timeline=timeline,active=True,last_frame=0,cover_key='same',scene_key=None,highlight=None,
        scene_index=0,prepared_lyrics=None,timing_state=None,labels=labels,scenes=Control(),**controls)
    view.show_timing=lambda state:KaraokeView.show_timing(view,state)
    all_controls=(*controls.values(),*stage_controls.values(),view.scenes,*(label for rows in labels for label in rows))
    return view,state,all_controls


class KaraokeRenderTests(unittest.TestCase):
    def test_stable_paused_frames_do_not_invalidate_gtk_layout_or_pango(self):
        view,state,controls=fixture()
        KaraokeView.frame(view,5,force=True)
        prepared=view.prepared_lyrics
        for control in controls:control.mutations=0
        with patch('karaoke.Pango.AttrList',side_effect=AssertionError('Unchanged words need no new Pango layout')):
            for frame in range(120):KaraokeView.frame(view,5+frame/30,force=True)
        self.assertIs(view.prepared_lyrics,prepared)
        self.assertIs(prepared.state,state)
        self.assertEqual(sum(control.mutations for control in controls),0)

    def test_word_fade_changes_exactly_at_supplied_times_and_seeks_back(self):
        line=LyricLine(1,'Тёплый свет',(LyricWord(1,2,0,7),LyricWord(2,3,7,11)))
        paint=WordHighlight(line)
        self.assertEqual(paint.attributes(.9).to_string(),'')
        self.assertIsNone(paint.attributes(.99))
        begin=paint.attributes(1).to_string()
        halfway=paint.attributes(1.06).to_string()
        finished=paint.attributes(1.12).to_string()
        self.assertNotEqual(begin,halfway);self.assertNotEqual(halfway,finished)
        self.assertIn('0 13 foreground',finished)  # Pango spans UTF-8 bytes.
        self.assertIsNone(paint.attributes(1.9))
        self.assertIsNotNone(paint.attributes(2))
        self.assertEqual(paint.attributes(.5).to_string(),'')

    def test_prepared_neighbours_keep_gaps_countdown_and_backwards_seek(self):
        state=LyricsState('ready',(LyricLine(2,'First'),LyricLine(4,''),LyricLine(8,'Second'),LyricLine(10,'')))
        prepared=LyricScenes(state)
        self.assertEqual(moment(state,1,prepared),('','♪','First',-1,1))
        self.assertEqual(moment(state,3,prepared),('','First','Second',0,None))
        self.assertEqual(moment(state,6,prepared),('First','♪','Second',1,2))
        self.assertEqual(moment(state,9,prepared),('First','Second','',2,None))
        self.assertEqual(moment(state,1,prepared),('','♪','First',-1,1))

    def test_prepared_frames_do_not_copy_or_rescan_full_song(self):
        class Lines(tuple):
            def __getitem__(self,index):
                if isinstance(index,slice):raise AssertionError('Frame copied the full lyrics')
                return super().__getitem__(index)
            def __iter__(self):
                if getattr(self,'prepared',False):raise AssertionError('Frame rescanned the full lyrics')
                return super().__iter__()
        lines=Lines(LyricLine(i*5,str(i)) for i in range(1000))
        state=LyricsState('ready',lines);prepared=LyricScenes(state);lines.prepared=True
        self.assertEqual(moment(state,2501,prepared),('499','500','501',500,None))
        self.assertEqual(moment(state,1001,prepared),('199','200','201',200,None))

    def test_ai_track_transition_holds_heard_metadata_then_updates_cache_and_seek(self):
        view,state,controls=fixture()
        new=LyricsState('ready',(LyricLine(0,'A new song'),))
        view.timeline.observe(PlaybackPoint(3,('new',),'New song','New artist',0,240,False,'same'),new)
        view.stage.lyrics.state=new;view.stage.lyrics.key=('new',)
        KaraokeView.frame(view,4,force=True)
        self.assertEqual(view.song.get_text(),'Fixture  ·  Artist')
        self.assertFalse(view.stage.progress.get_sensitive())
        self.assertFalse(view.import_button.get_sensitive())
        self.assertIs(view.prepared_lyrics.state,state)
        KaraokeView.frame(view,5,force=True)
        self.assertEqual(view.song.get_text(),'New song  ·  New artist')
        self.assertTrue(view.stage.progress.get_sensitive())
        self.assertTrue(view.import_button.get_sensitive())
        self.assertIs(view.prepared_lyrics.state,new)
        view.audio.active=False
        view.timeline.observe(PlaybackPoint(6,('new',),'New song','New artist',30,240,False,'same'),new)
        KaraokeView.frame(view,6,force=True)
        self.assertIsNone(view.delayed_length)
        view.audio.active=True;view.audio.delay=0
        view.timeline.observe(PlaybackPoint(7,('new',),'New song','New artist',4,240,False,'same'),new)
        KaraokeView.frame(view,7,force=True)
        self.assertEqual(view.stage.progress.get_value(),4)


if __name__=='__main__':unittest.main()
