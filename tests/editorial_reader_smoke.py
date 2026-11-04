"""Offline GTK reader: motion, real worker latency, responsive UI and no reflow."""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0')
from gi.repository import Gtk,Gdk,GLib
from editorial_reader import EditorialReader,CSS
from editorial_translation import EditorialTranslator,TranslationCache,TranslationError
from editorial_motion import ReaderFocus

ORIGINAL=('Recorded in the quiet hours, this album finds its character in the space between instruments. '
    'Warm synthesisers meet a close, unhurried rhythm section; small details appear each time the music returns.\n\n'
    'The musicians approached every song as a conversation. A melody might begin on the piano, move to the guitar '
    'and settle into a different colour by the final chorus. Nothing is rushed, and nothing is there by accident.\n\n'
    'Across these recordings, change is a recurring theme: familiar sounds take unexpected turns, '
    'while the songs keep a sense of intimacy. It is a record made to be heard from beginning to end.')
RUSSIAN=('Записанный в тихие часы, этот альбом обретает характер в пространстве между инструментами. '
    'Тёплые синтезаторы встречаются с неторопливой ритм-секцией, а при каждом новом прослушивании открываются небольшие детали.\n\n'
    'Музыканты подходили к каждой песне как к разговору. Мелодия могла зародиться на фортепиано, перейти к гитаре '
    'и к последнему припеву зазвучать совсем иначе. Здесь ничто не торопится и ничто не возникает случайно.\n\n'
    'Сквозная тема этих записей — перемены: знакомые звуки принимают неожиданные формы, '
    'а песни сохраняют ощущение близости. Этот альбом создан для прослушивания от начала до конца.')


def settle(seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        for _ in range(4):
            if GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.004)


def wait(predicate):
    end=time.monotonic()+3
    while not predicate() and time.monotonic()<end:settle(.02)
    assert predicate(),'Reader worker did not complete'


def run():
    entered=threading.Event();release=threading.Event();calls=[]
    def translate(value,alive):
        calls.append(value);entered.set();assert release.wait(2)
        return RUSSIAN
    provider=Gtk.CssProvider();provider.load_from_data(b'.ember-stage { background-color: #15221c; }'+CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    with tempfile.TemporaryDirectory() as folder:
        client=EditorialTranslator(TranslationCache(folder),translate)
        window=Gtk.Window();window.set_default_size(1280,900);window.get_style_context().add_class('ember-stage')
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);outer.set_border_width(36)
        scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.add(outer);window.add(scroll)
        card=EditorialReader(ORIGINAL,'The Quiet Hours','Ember Sessions',client,album=True)
        outer.pack_start(card,False,False,0);window.show_all();settle(.7)
        assert not calls,'Opening a description must never translate automatically'
        assert card.original_label.get_selectable() and card.original_label.get_text()==ORIGINAL
        card.translate_button.clicked();assert entered.wait(1);settle(.15)
        assert card.loading and card.original_label.get_mapped() and card.pulse
        beats=[];idle=GLib.timeout_add(16,lambda:(beats.append(1),True)[1]);settle(.2);GLib.source_remove(idle)
        assert len(beats)>=8,'A translation blocked the GTK thread'
        release.set();wait(lambda:not card.loading);settle(.65)
        assert card.pages.get_visible_child_name()=='russian' and card.russian_label.get_text()==RUSSIAN
        assert not card.pulse and not card.progress.get_visible()
        before=card.pages.get_allocated_height()
        card.translate_button.clicked();heights=[]
        for _ in range(18):settle(.032);heights.append(card.pages.get_allocated_height())
        assert set(heights)=={before},'Crossfade must not reflow the article every frame'
        assert card.pages.get_visible_child_name()=='original'
        card.translate_button.clicked();settle(.6);assert len(calls)==1
        preview=os.environ.get('EMBERBOX_EDITORIAL_PREVIEW')
        if preview:
            window.set_focus(None);settle(.1)
            Gdk.pixbuf_get_from_window(window.get_window(),0,0,*window.get_size()).savev(preview,'png',[],[])
        for width,height in ((1024,600),(700,700),(1920,1080)):
            window.resize(width,height);settle(.25)
            assert window.get_size()==(width,height)
            assert card.get_allocated_width()<=scroll.get_allocated_width()
            x,y=card.translate_button.translate_coordinates(window,0,0)
            assert x>=0 and x+card.translate_button.get_allocated_width()<=width
        window.resize(1024,600)
        spacer=Gtk.Box();spacer.set_size_request(-1,220);outer.pack_start(spacer,False,False,0)
        outer.reorder_child(spacer,0);spacer.show();settle(.15)
        focus=ReaderFocus(scroll,outer);scroll.get_vadjustment().set_value(0)
        focus.begin(card);settle(.16)
        assert focus.tick and scroll.get_vadjustment().get_value()>0
        focus.interrupted();assert not focus.tick and not focus.wait
        focus.begin(card);settle(.7)
        assert not focus.tick and not focus.wait and scroll.get_vadjustment().get_value()>100
        card.destroy();assert card.closed and not card.pulse and not card.entrance_idle
        # The same already-requested article reopens translated without a new job.
        card=EditorialReader(ORIGINAL,'The Quiet Hours','Ember Sessions',client,album=True)
        outer.pack_start(card,False,False,0);card.show_all();wait(lambda:card.result is not None)
        assert len(calls)==1
        card.destroy();client.close();window.destroy();settle(.1)
        # Failure never swaps away the original. Retry remains available.
        client=EditorialTranslator(TranslationCache(folder),lambda *_a,**_k:(_ for _ in ()).throw(TranslationError('offline')))
        window=Gtk.Window();card=EditorialReader('Another original.','Story','Service',client);window.add(card);window.show_all();settle(.1)
        card.translate_button.clicked();wait(lambda:not card.loading)
        assert card.pages.get_visible_child_name()=='original' and card.translate_button.get_sensitive()
        assert card.status.get_style_context().has_class('editorial-error')
        window.destroy();client.close();settle(.1)
        settings=Gtk.Settings.get_default();motion=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False)
        client=EditorialTranslator(TranslationCache(folder),translate)
        window=Gtk.Window();card=EditorialReader('Original <b>literal</b> & text.','Story','Service',client)
        window.add(card);window.show_all();settle(.1)
        assert card.entrance.get_transition_duration()==0 and card.original_label.get_text()=='Original <b>literal</b> & text.'
        card.translate_button.clicked();wait(lambda:not card.loading)
        assert not card.pulse and card.pages.get_transition_duration()==0
        window.destroy();client.close();settings.set_property('gtk-enable-animations',motion)
        # Late work must not touch a destroyed card or another artist's prose.
        entered.clear();release.clear();client=EditorialTranslator(TranslationCache(folder),translate)
        window=Gtk.Window();card=EditorialReader('An old artist.','Old artist','Service',client)
        window.add(card);window.show_all();settle(.1);card.translate_button.clicked();assert entered.wait(1)
        window.destroy();release.set();settle(.2);assert card.result is None and card.closed
        client.close()
    print('PASS: editorial reader, Russian/original crossfade, worker responsiveness, layout, cache and stale work')


if __name__=='__main__':run()
