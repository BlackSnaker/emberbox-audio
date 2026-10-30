"""Real GTK album-room regression checks with original, offline demo media.

Run under Xvfb, for example::

    xvfb-run -a -s '-screen 0 1920x1080x24' /usr/bin/python3 tests/album_room_smoke.py

Set EMBERBOX_ALBUM_PREVIEW to a folder to run both English and Russian UI
fixtures and save full-window screenshots there. No account or network is used.
"""
import copy
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


# Language is selected when source_picker is imported. Separate child processes
# exercise the actual translated UI rather than changing its module constants.
if __name__ == '__main__' and os.environ.get('EMBERBOX_ALBUM_PREVIEW') and '--preview-child' not in sys.argv:
    for language in ('en', 'ru'):
        child_env = dict(os.environ, EMBERBOX_LANGUAGE=language)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--preview-child'],
                       env=child_env, check=True)
    raise SystemExit(0)

import fullscreen_smoke as f
import fullscreen
from source_picker import text
from gi.repository import Gdk, Gtk


TITLE = text('Afterglow', 'Послесвечение')
ARTIST = 'Emberbox Sessions'
LONG_TITLES = (
    'Letters from the Observatory — Original Evening Sessions with the Paper Satellites '
    '(Unabridged Anniversary Edition / A Collection of Quiet Songs)',
    'Письма из старой обсерватории — музыка тёплого воздуха с участием Северной комнаты '
    '(полное юбилейное издание вечерних записей и тихих песен)',
)
NAMES = (
    ('Afterglow', 'Послесвечение'), ('The Shape of Amber', 'Форма янтаря'),
    ('An Unavailable Recording', 'Недоступная запись'), ('A Quiet Orbit', 'Тихая орбита'),
    ('Slow-burning Light', 'Медленный свет'),
    ('A Long Way Home — Live at the Old Observatory (Expanded Evening Edition)',
     'Долгая дорога домой — концерт в старой обсерватории (полное вечернее издание)'),
    ('Amber Signals', 'Янтарные сигналы'), ('Between Two Stations', 'Между станциями'),
    ('A Soft Place to Land', 'Место для тихого приземления'),
    ('We Keep the Light On', 'Мы оставляем свет'), ('Small Hours', 'Ночные часы'),
    ('One More Quiet Evening', 'Ещё один тихий вечер'),
)
TRACKS = [
    {'id': str(index), 'uri': f'spotify:track:{index}', 'title': text(*names),
     'artist': ARTIST, 'artistId': 'DEMOARTIST', 'album': TITLE,
     'image': 'fixture:original-cover', 'duration_ms': (170+index*11)*1000,
     'playable': index != 3}
    for index, names in enumerate(NAMES, 1)
]
RELEASE = {
    'id': 'DEMOALBUM', 'uri': 'spotify:album:DEMOALBUM', 'kind': 'album',
    'title': TITLE, 'artist': ARTIST, 'artistId': 'DEMOARTIST',
    'artistUri': 'spotify:artist:DEMOARTIST', 'image': 'fixture:original-cover',
    'releaseDate': '2026-10-23', 'trackCount': len(TRACKS),
    'description': text(
        'Original demonstration liner notes.\n\nAfterglow is a fictional collection about '
        'warmth, memory and the sound of a room after sunset. Each recording follows a small '
        'detail: an open window, a late train, a light left on for someone coming home.\n\n'
        'These songs, credits and artwork are original demonstration material. The album room '
        'keeps the whole collection in order and makes space to read while the music continues.',
        'Оригинальные заметки к демонстрационному альбому.\n\n«Послесвечение» — вымышленный '
        'сборник о тепле, памяти и звуках комнаты после заката. Каждая запись следует за '
        'небольшой деталью: открытым окном, поздним поездом, светом для возвращающегося домой.\n\n'
        'Песни, подписи и обложка созданы для демонстрации. Комната альбома сохраняет порядок '
        'композиций и оставляет место для чтения, пока музыка продолжается.'),
    'copyright': 'Original fixture © 2026 Emberbox Sessions',
}
PROFILE = {'id': 'DEMOARTIST', 'name': ARTIST, 'image': 'fixture:original-cover',
           'bio': 'Original demonstration artist biography.'}


def wait(predicate, message='Album request did not finish', limit=4):
    deadline = time.monotonic()+limit
    while not predicate() and time.monotonic() < deadline:
        f.settle(.03)
    assert predicate(), message
    f.settle(.08)


def ready(view):
    wait(lambda: not view.busy and len(view.song_buttons) == len(TRACKS)
         and getattr(view, 'release_tracks', None) is not None)
    wait(lambda: not view.entrance.busy, 'Album entrance did not finish')
    # The album may have its own finite entrance, separate from artist reveal.
    f.settle(.8)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def rectangle(widget, parent):
    point = widget.translate_coordinates(parent, 0, 0)
    assert point is not None, ('Widget must belong to the album window', type(widget).__name__)
    allocation = widget.get_allocation()
    return (*point, allocation.width, allocation.height)


def contained(inner, outer, message):
    x, y, width, height = inner
    ox, oy, ow, oh = outer
    assert x >= ox-1 and y >= oy-1 and x+width <= ox+ow+2 and y+height <= oy+oh+2, \
        (message, inner, outer)


def bottom_controls(stage):
    return (stage.play_button, stage.previous_button, stage.next_button,
            stage.progress, stage.knob, stage.volume_meter, stage.mute)


def fits(stage, widgets):
    width, height = stage.window.get_size()
    for widget in widgets:
        assert widget.get_mapped(), ('Control is not visible', type(widget).__name__)
        contained(rectangle(widget, stage.window), (0, 0, width, height),
                  'Album controls must fit the requested window')


def geometry(stage, view, width, height):
    assert stage.window.get_size() == (width, height), 'Album content forced a wider or taller window'
    fits(stage, (view.back_button, view.refresh_button, view.scroll, *bottom_controls(stage)))
    assert view.content.get_allocated_width() <= view.scroll.get_allocated_width()+2, \
        'Album content overflowed horizontally'
    horizontal = view.scroll.get_hadjustment()
    assert horizontal.get_upper() <= horizontal.get_page_size()+2, \
        'The album must not require horizontal scrolling'
    hero = view.release_hero
    assert hero.get_mapped() and hero.cover.get_mapped()
    cover = rectangle(hero.cover, stage.window)
    contained(cover, rectangle(hero, stage.window), 'The complete artwork must fit inside the album header')
    contained(cover, rectangle(view.scroll, stage.window), 'The complete artwork must fit the first screen')
    assert min(cover[2:]) >= (250 if width == 1920 else 100 if height == 600 else 120), \
        ('Album artwork must be substantial', (width, height), cover)
    assert abs(cover[2]-cover[3]) <= 2, ('The original square cover must stay square', cover)
    pixels = hero.cover.get_pixbuf()
    assert pixels is not None and pixels.get_width() <= cover[2]+2 and pixels.get_height() <= cover[3]+2, \
        'The album cover must render completely, without clipping its pixels'
    fits(stage, (hero.play_button, hero.queue_button, hero.artist_button, hero.notes_button))
    # Track text may be below the viewport, but its complete row must retain
    # horizontal space for the title, duration and independent queue control.
    for row in view.release_tracks.rows:
        x, _, row_width, _ = rectangle(row, stage.window)
        assert x >= 0 and x+row_width <= width+2, ('Track row overflow', x, row_width, width)
        assert row.name.get_allocated_width() >= width*.28, \
            ('Track titles lost their readable column', width, row.name.get_allocated_width())
    if height == 600:
        first_row = view.release_tracks.rows[0]
        assert first_row.get_mapped(), 'The first recording must appear on the small-screen album page'
        contained(rectangle(first_row, stage.window), rectangle(view.scroll, stage.window),
                  'The first recording must fit completely below the compact album header')


def screenshot(stage, name):
    output = os.environ.get('EMBERBOX_ALBUM_PREVIEW')
    if not output:
        return
    language = 'ru' if os.environ.get('EMBERBOX_LANGUAGE', '').startswith('ru') else 'en'
    folder = Path(output)/language
    folder.mkdir(parents=True, exist_ok=True)
    stage.window.set_focus(None)
    f.settle(.2)
    width, height = stage.window.get_size()
    Gdk.pixbuf_get_from_window(stage.window.get_window(), 0, 0, width, height).savev(
        str(folder/(name+'.png')), 'png', [], [])


def run():
    host = f.FixtureHost()
    host.title.set_text(TRACKS[0]['title'])
    host.artist.set_text(ARTIST)
    host.album.set_text(TITLE)
    host.session = SimpleNamespace(metadata={'xesam:url': TRACKS[0]['uri']})
    host.youtube = SimpleNamespace(queue=[], current=None, eof=False, paused=True, mpv=None)
    calls, plays = [], []
    entered, release = threading.Event(), threading.Event()
    block_browse = [True]
    play_entered, finish_play = threading.Event(), threading.Event()
    block_play = [False]

    def load(source, category, term='', collection=None, offset=0):
        calls.append((source, category, copy.deepcopy(collection or {}), offset))
        if block_browse[0]:
            entered.set()
            assert release.wait(4), 'Fixture release request was not released'
        if category == 'release':
            return {'release': copy.deepcopy(RELEASE), 'items': copy.deepcopy(TRACKS), 'next': None}
        assert category == 'artist', ('Unexpected fixture request', category)
        return {'artist': dict(PROFILE), 'sections': [
            {'id': 'latest-release', 'items': [copy.deepcopy(RELEASE)]},
            {'id': 'top-songs', 'items': copy.deepcopy(TRACKS[:4])}]}

    def play(item, alive):
        if not alive():
            return
        plays.append(item['uri'])
        if block_play[0]:
            play_entered.set()
            assert finish_play.wait(4), 'Fixture playback request was not released'

    real_image_load = fullscreen.Artwork.load

    def artwork(loader, image, _url, size, radius=8, **options):
        return real_image_load(loader, image, (f.ROOT/'assets/demo-cover.png').as_uri(),
                               size, radius, **options)

    with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network access')), \
         patch('music_library.LocalSpotify', side_effect=AssertionError('Unexpected private account access')), \
         patch.object(fullscreen, 'LyricsClient', f.FixtureLyrics), \
         patch.object(fullscreen.Artwork, 'load', artwork):
        stage = fullscreen.FullscreenPlayer(host)
        host.fullscreen = stage
        service, view = stage.music, stage.artist_view
        service.repository.load, service.repository.play = load, play
        try:
            stage.open()
            f.wait_transition(stage)
            stage.window.unfullscreen()
            stage.window.resize(1920, 1080)
            f.settle(.3)
            assert not calls and not plays and not host.calls
            paints = [0]
            stage.window.get_frame_clock().connect(
                'after-paint', lambda *_: paints.__setitem__(0, paints[0]+1))
            begin = view.album_opening.begin
            opening_states = []

            def begin_opening(hero, records):
                begin(hero, records)
                opening_states.append((view.album_opening.busy, hero.get_opacity(), records.get_opacity()))

            with patch.object(view.album_opening, 'begin', side_effect=begin_opening) as opening:
                stage.album_button.clicked()
                wait(entered.is_set)
                assert len(calls) == 1 and calls[0][1] == 'release', \
                    'Opening the current album must request the album before any artist catalogue'
                assert calls[0][2]['songUri'] == TRACKS[0]['uri']
                before_paints = paints[0]
                f.settle(.25)
                assert paints[0] > before_paints, 'Loading an album blocked GTK painting'
                assert not plays and not host.calls, 'Album navigation must not send playback commands'
                block_browse[0] = False
                release.set()
                ready(view)
                opening.assert_called_once_with(view.release_hero, view.release_tracks)
                if Gtk.Settings.get_default().get_property('gtk-enable-animations'):
                    assert opening_states[0][0] and all(0 < opacity < 1 for opacity in opening_states[0][1:]), \
                        'Direct album opening must execute its finite entrance'
                assert not view.album_opening.busy
                assert view.release_hero.get_opacity() == view.release_tracks.get_opacity() == 1., \
                    'The album entrance must finish with the header and recordings fully visible'
            assert stage.page == 'artist' and view.direct_release
            assert view.release_ref['id'] == RELEASE['id']
            assert not any(category == 'artist' for _, category, _, _ in calls)
            assert not view.filter_bar.get_visible(), 'Album navigation must not show artist catalogue filters'
            assert len(view.release_tracks.rows) == len(TRACKS)
            assert [value['uri'] for _, _, value in view.song_buttons] == [item['uri'] for item in TRACKS]
            assert view.read_button is view.release_hero.notes_button
            assert [widget for widget in descendants(view) if isinstance(widget, Gtk.ScrolledWindow)] == [view.scroll], \
                'Header, notes and tracks must use a single scrolling surface'
            for control in (view.release_hero.play_button, view.release_hero.queue_button,
                            view.release_hero.artist_button, view.release_hero.notes_button,
                            *[button for play_button, add_button, _ in view.song_buttons
                              for button in (play_button, add_button)]):
                assert control.get_accessible().get_name(), 'Every album action needs an accessible name'
                assert not control.get_has_tooltip(), 'Album controls must not summon text tooltips'

            # An unavailable recording remains in its real album position.
            unavailable = view.release_tracks.rows[2]
            assert not unavailable.get_activatable()
            assert not view.song_buttons[2][0].get_sensitive() and not view.song_buttons[2][1].get_sensitive()
            unavailable.activate()
            f.settle(.1)
            assert not plays and not service.book.upcoming('spotify')

            # Each queue action is independent of both row activation and play.
            view.song_buttons[0][1].clicked()
            f.settle(.04)
            assert view.notice.get_mapped() and view.notice.get_text(), \
                'Adding a recording must show visible queue feedback'
            assert not plays and [item['id'] for _, item in service.book.upcoming('spotify')] == ['1']
            view.song_buttons[1][0].clicked()
            wait(lambda: not service.loading)
            assert plays == [TRACKS[1]['uri']], 'One track-title click must dispatch exactly one play request'
            assert [item['id'] for _, item in service.book.upcoming('spotify')] == [
                '1', *[item['id'] for item in TRACKS[3:]]], \
                'Playback must preserve manual additions, then continue the album in order without unavailable tracks'
            view.release_tracks.rows[3].activate()
            wait(lambda: not service.loading)
            assert plays == [TRACKS[1]['uri'], TRACKS[3]['uri']], \
                'One row activation must dispatch exactly one play request'

            # Header actions apply to the whole playable release in album order.
            playable = [item['uri'] for item in TRACKS if item.get('playable') is not False]
            service.book.replace('spotify', [])
            service.changed()
            before = list(plays)
            view.release_hero.queue_button.clicked()
            f.settle(.04)
            assert view.notice.get_mapped() and view.notice.get_text(), \
                'Adding the album must show visible queue feedback'
            assert plays == before
            assert [item['uri'] for _, item in service.book.upcoming('spotify')] == playable
            view.release_hero.play_button.clicked()
            wait(lambda: not service.loading)
            assert plays == before+[playable[0]], 'Play album must begin at its first available track once'
            assert [item['uri'] for item in service.book.queues['spotify']] == playable
            assert all(item['origin'] == 'context' for item in service.book.queues['spotify'])
            assert [item['uri'] for _, item in service.book.upcoming('spotify')] == playable[1:]

            # The common scroll grows to fit notes; reading never changes music.
            adjustment = view.scroll.get_vadjustment()
            adjustment.set_value(0)
            f.settle(.1)
            upper = adjustment.get_upper()
            original_plays = list(plays)
            view.read_button.clicked()
            f.settle(.45)
            assert view.notes_revealer.get_reveal_child() and view.notes_revealer.get_child_revealed()
            assert adjustment.get_upper() > upper+60, 'Opening liner notes must extend the main album scroll'
            assert any(RELEASE['description'].split('\n')[0] in value
                       for value in f.labels(view.notes_revealer))
            assert not any(isinstance(widget, Gtk.ScrolledWindow)
                           for widget in descendants(view.notes_revealer)), 'Liner notes must not have a nested scrollbar'
            assert plays == original_plays and not host.calls
            screenshot(stage, 'album-notes-1920')
            view.read_button.clicked()
            f.settle(.45)
            assert not view.notes_revealer.get_reveal_child()

            # Track and pause changes update rows in place and retain reading position.
            table = view.release_tracks
            rows = tuple(table.rows)
            adjustment.set_value(min(300, adjustment.get_upper()-adjustment.get_page_size()))
            f.settle(.1)
            position = adjustment.get_value()
            assert position > 0, 'The complete album track list must remain scrollable'
            for index, playing in ((4, True), (4, False), (5, True)):
                item = TRACKS[index]
                host.title.set_text(item['title'])
                host.artist.set_text(item['artist'])
                host.session.metadata['xesam:url'] = item['uri']
                host.length, host.position, host.playing = item['duration_ms']*1000, 12_000_000, playing
                stage.update()
                f.settle(.12)
                assert view.release_tracks is table and tuple(table.rows) == rows, \
                    'Current-track changes must not rebuild the album rows'
                assert abs(adjustment.get_value()-position) < 1, 'Playback changes moved the album reading position'
                assert rows[index].get_style_context().has_class('record-current')
                assert rows[index].rank.get_visible_child_name() == 'current'
                assert rows[index].indicator.get_icon_name()[0] == (
                    'media-playback-start-symbolic' if playing else 'media-playback-pause-symbolic')
                assert sum(row.get_style_context().has_class('record-current') for row in rows) == 1
            assert plays == original_plays and not host.calls, 'Metadata updates must not issue transport commands'

            # A slow selected song exposes pending state without destroying the list.
            block_play[0] = True
            rows[6].activate()
            wait(play_entered.is_set)
            assert rows[6].get_style_context().has_class('record-pending')
            assert rows[6].rank.get_visible_child_name() == 'pending'
            assert view.release_tracks is table and tuple(table.rows) == rows
            finish_play.set()
            block_play[0] = False
            wait(lambda: not service.loading)
            assert not rows[6].get_style_context().has_class('record-pending')

            # Full GTK allocations cover desktop, laptop and small-screen windows.
            for width, height in ((1920, 1080), (1280, 720), (1024, 600)):
                stage.window.unfullscreen()
                stage.window.resize(width, height)
                f.settle(.4)
                view.scroll.get_vadjustment().set_value(0)
                f.settle(.1)
                geometry(stage, view, width, height)
                screenshot(stage, f'album-{width}')
                controls = {widget: rectangle(widget, stage.window) for widget in bottom_controls(stage)}
                for title in LONG_TITLES:
                    view.release['title'] = title
                    view.render()
                    f.settle(.45)
                    view.scroll.get_vadjustment().set_value(0)
                    f.settle(.1)
                    geometry(stage, view, width, height)
                    for widget, original in controls.items():
                        assert rectangle(widget, stage.window) == original, \
                            ('A long album title displaced a bottom control', title, type(widget).__name__)
                screenshot(stage, f'album-long-title-{width}')
                view.release['title'] = TITLE
                view.render()
                f.settle(.3)

            # Artist navigation belongs to this release, even after host metadata changes.
            before = list(plays)
            host.artist.set_text('An unrelated current performer')
            view.release_hero.artist_button.clicked()
            wait(lambda: view.profile is not None and view.profile.get('id') == PROFILE['id']
                 and view.release_ref is None)
            assert calls[-1][1] == 'artist' and calls[-1][2]['id'] == PROFILE['id']
            assert calls[-1][2]['name'] == ARTIST
            assert plays == before and not host.calls, 'Opening the album artist also played music'
            view.back_button.clicked()
            f.settle(.2)
            assert stage.page == 'playing'

            # Direct album back returns to the listening page without artist loading.
            host.artist.set_text(ARTIST)
            host.album.set_text(TITLE)
            stage.update()
            stage.album_button.clicked()
            ready(view)
            requests = len(calls)
            view.back_button.clicked()
            f.settle(.2)
            assert stage.page == 'playing' and len(calls) == requests and plays == before
            print('PASS album room: direct loading, independent actions, ordered context, unavailable rows, '
                  'single-scroll notes, stable playback rows, bilingual long titles and three full-window sizes')
        finally:
            release.set()
            finish_play.set()
            stage.close()
            host.window.destroy()


if __name__ == '__main__':
    run()
