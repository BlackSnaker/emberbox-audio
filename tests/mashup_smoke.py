"""Offline fullscreen studio: all sizes, source boundaries, recipes, routing."""
import os
from pathlib import Path
from unittest.mock import patch,Mock
import fullscreen_smoke as f
import fullscreen
from gi.repository import Gtk,Gdk

host=f.FixtureHost()
items=[{'source':'ccmixter','id':str(i),'title':title,'artist':'Ember Sessions',
    'license':'https://creativecommons.org/licenses/by/4.0/','page':'https://ccmixter.org/files/fixture/'+str(i),
    'duration':60,'bpm':120,'kind':kind}
    for i,title,kind in [(101,'A voice in amber','vocal'),(102,'The shape of the evening','instrumental')]]

with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.open();f.wait_transition(stage);stage.show_page('mashup');f.settle(.3)
        view=stage.mashups
        assert view.active and view.get_mapped()
        view.catalog.search=lambda *_a:items
        view.choose(0);f.settle(.3)
        assert len(view.results.get_children())==2 and not host.calls
        view.select(items[0],0);view.select(items[1],1)
        view.choose(1);f.settle(.3)
        assert view.catalogue_query[1]=='instrumental','Deck B must refresh the catalogue to instrumentals'
        view.page('studio')
        assert view.prepare_button.get_sensitive()
        with patch.object(view.client,'prepare') as prepare:
            view.prepare_button.clicked();assert prepare.call_count==1
            assert prepare.call_args.args[0]['tracks'][0]['source']=='ccmixter'
        view.name.set_text('Two original streams');view.save()
        assert len(view.store.items)==1
        view.page('projects');assert view.projects.get_children()
        view.open_project(view.store.items[0]);assert view.tracks[0]['id']=='101'
        assert view.current()['tracks'][1]['role']=='instrumental'
        view.select({'source':'spotify','id':'blocked','title':'A subscription recipe','artist':'Fixture'},0)
        with patch.object(view.client,'prepare') as prepare:
            view.prepare_button.clicked();assert not prepare.called,'Subscription streams must never enter this decoder path'
        view.select(items[0],0)
        for width,height in ((1920,1080),(1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);f.settle(.35)
            assert stage.window.get_size()==(width,height),('Studio overflow',stage.window.get_size())
            for widget in (view.tabs,view.actions,view.prepare_button,view.save_button,stage.play_button,stage.knob,stage.progress):
                x,y=widget.translate_coordinates(stage.window,0,0)
                assert x>=0 and y>=0 and x+widget.get_allocated_width()<=width+1 and y+widget.get_allocated_height()<=height+1
            assert view.content.get_allocated_width()<=view.pages.get_allocated_width()+1
        stage.window.resize(1920,1080);f.settle(.3)
        assert view.hero.get_allocated_height()<=110,'Studio heading consumes too much working space'
        for deck in view.decks:
            x,y=deck['box'].translate_coordinates(stage.window,0,0)
            assert y+deck['box'].get_allocated_height()<=view.actions.translate_coordinates(stage.window,0,0)[1]
        view.client.state='ready';view.client.paused=True;view.client.ready={'duration':30,'waves':[[.1,.5,.3]*85]*2,'plan':{'tempo':120}}
        view.autoplay=False;view.changed();stage.update();f.settle(.1)
        view.decks[1]['gain'].set_value(.6)
        assert view.dirty and view.current()['tracks'][1]['gain']==.6
        assert stage.progress.get_sensitive() and stage.total.get_text()=='0:30'
        before=list(host.calls)
        with patch.object(view.client,'toggle') as toggle:stage.play_button.clicked();assert toggle.call_count==1
        with patch.object(view.client,'seek') as seek:stage.request_seek(10);seek.assert_called_once_with(10)
        with patch.object(view.client,'set_volume') as volume:stage.set_volume(.5);volume.assert_called_once_with(.5)
        assert host.calls==before,'Mashup controls must not operate the subscription player'
        preview=os.environ.get('EMBERBOX_MASHUP_PREVIEW')
        if preview:
            stage.window.set_focus(None);f.settle(.2)
            Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,*stage.window.get_size()).savev(preview,'png',[],[])
        stage.show_page('playing');assert view.client.state=='idle' and not view.active
        print('PASS fullscreen mashup studio, free stream selection, source boundaries, recipes, transport and three sizes')
    finally:stage.close();host.window.destroy()
