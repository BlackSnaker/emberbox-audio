"""Offline heart animation, shared state and cross-source collection controls."""
from pathlib import Path
import os,sys,tempfile,time
from types import SimpleNamespace as NS
root=Path(__file__).resolve().parents[1]
fixture=tempfile.TemporaryDirectory(prefix='ember-favorite-ui-')
os.environ['XDG_CONFIG_HOME']=fixture.name
sys.path.insert(0,str(root/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
from favorite_button import FavoriteButton,CSS,heart_frame,FRAME_STEPS,CONFIRMATION_MS
from favorites import Favorites
from listening_library import LibraryView,CSS as LIBRARY_CSS
from listening_queue import track


def settle(seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.003)


def wait(until):
    end=time.monotonic()+4
    while not until() and time.monotonic()<end:settle(.02)
    assert until(),'Favourite UI timed out'


class Music:
    def __init__(self):
        self.host=NS(source='spotify',spotify_mode='native',spotify_web=NS(state={'uri':'spotify:track:FIXTURE','id':'FIXTURE'},connected=False),
            apple_mode='native',apple_web=NS(state={'id':'123'},connected=False),
            title=Gtk.Label(label='Afterglow'),artist=Gtk.Label(label='Ember Sessions'),album=Gtk.Label(label='Vol. 01'),
            art_url='',playing=False,length=180_000_000,position=0)
        self.host.select_source=lambda source:setattr(self.host,'source',source)
        self.favorites=Favorites(self,Path(fixture.name)/'favorites.json');self.loading=False;self.error='';self.plays=[]
    def subscribe(self,_callback):return lambda:None
    def cancel_browse(self):pass
    def play_now(self,item,context=None):self.plays.append((item,context))


music=Music();favorites=music.favorites
window=Gtk.Window();box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);window.add(box)
provider=Gtk.CssProvider();provider.load_from_data(CSS+LIBRARY_CSS)
Gtk.StyleContext.add_provider_for_screen(window.get_screen(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
hearts=Gtk.Box();first=FavoriteButton(favorites,38);second=FavoriteButton(favorites,48)
hearts.pack_start(first,False,False,0);hearts.pack_start(second,False,False,0);box.pack_start(hearts,False,False,0)
art=NS(load=lambda *_a,**_k:None)
view=LibraryView(music,art,lambda:None);box.pack_start(view,True,True,0)
window.set_default_size(1000,600);window.show_all();settle()
settings=first.get_settings();animations=settings.get_property('gtk-enable-animations');settings.set_property('gtk-enable-animations',True)
try:
    first.clicked();wait(lambda:first.target==1.)
    assert first.tick and second.tick,'Both visible hearts must animate from shared confirmation'
    settle(.25);assert 0<first.shown<1 and first.note.get_visible()
    settle(.7);assert .95<first.shown<1 and first.tick,'The filament must warm gradually instead of snapping to its final colour'
    wait(lambda:not first.tick and not second.tick)
    assert first.shown==1
    wait(lambda:not first.note.get_visible())
    assert not first.note_tick and not first.timeout,'Brief confirmation must finish both opacity motion and its timer'
    assert not first.get_has_tooltip() and not first.note.get_modal()
    wait(lambda:not favorites.pending)
    # Updating account details while the chip is visible must not restart its
    # lifetime. The full detail remains available to assistive technology.
    item=favorites.current();favorites.feedback[item['uri']]={'phase':'synced','saved':True}
    first.feedback('Full account confirmation',item);settle(.3);timer=first.timeout
    first.feedback('Updated account detail',item)
    assert first.timeout==timer and first.caption.get_text()=='In your favourites'
    settle(CONFIRMATION_MS/1000);assert not first.note.get_visible()
    apple=track(dict(uri='apple:songs:123',title='Original fixture',artist='Ember'), 'apple-music')
    favorites.set(apple,True);wait(lambda:not favorites.pending)
    view.active=True;view.category='favorites';view.load();settle()
    assert len(view.favorite_tables)==2 and len(view.song_buttons)==2
    view.song_buttons[1][0].clicked()
    assert music.host.source=='apple-music' and music.plays[-1][0]['uri']==apple['uri']
    # Refreshing the selected source must retain the all-source favourites tab.
    view.activate();assert view.category=='favorites' and len(view.favorite_tables)==2
    view.song_buttons[1][1].clicked();wait(lambda:not favorites.pending)
    assert len(view.song_buttons)==1
    music.host.source='spotify';favorites.refresh()
    settings.set_property('gtk-enable-animations',False)
    first.clicked();wait(lambda:not favorites.pending)
    assert first.shown==0 and not first.tick and second.shown==0
    settings.set_property('gtk-enable-animations',True)
    first.clicked();wait(lambda:first.target==1.)
    first.hide();assert not first.tick and not first.timeout and not first.note_tick
    # Cold vector frame work is small and bounded; settled buttons do none.
    durations=[]
    for index in range(FRAME_STEPS+1):
        started=time.perf_counter();heart_frame(index,48);durations.append(time.perf_counter()-started)
    print('PASS shared favourites, cross-source playback/removal, reduced motion and finite heart animation; slowest sprite',round(max(durations)*1000,2),'ms')
finally:
    settings.set_property('gtk-enable-animations',animations)
    view.close();window.destroy();favorites.close();fixture.cleanup()
