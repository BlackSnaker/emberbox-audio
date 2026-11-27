"""GTK credit cards shared by the desktop widget and listening room."""
from concurrent.futures import ThreadPoolExecutor

from gi.repository import GLib, Gtk, Pango

from recording_credits import current_recording, people
from source_picker import text
from spotify_artwork import artist_image


CSS = b'''
popover.ember-credits { background-color: #242321; color: #f0e2c4; padding: 5px;
  border: 1px solid rgba(232,204,159,.36); border-radius: 23px;
  box-shadow: 0 12px 30px rgba(10,8,6,.32); }
.ember-credit-sheet, .ember-credit-panel {
  padding: 14px 16px; border-radius: 17px;
  background-image: radial-gradient(ellipse at top left, rgba(230,169,94,.15), transparent 72%),
    linear-gradient(148deg,rgba(210,200,184,.095),rgba(110,105,100,.025) 50%,rgba(210,200,184,.065));
  border: 1px solid rgba(234,213,176,.13);
  box-shadow: inset 0 1px rgba(255,238,206,.12), inset 0 -1px rgba(17,13,10,.24); }
.ember-credit-title { font-size: 21px; font-weight: bold; color: #f5e8cf; }
.ember-credit-role { font-size: 11px; color: #d8bd88; letter-spacing: .35px; }
.ember-credit-note { font-size: 11px; color: #c9bda7; }
.ember-credit-note, .ember-credit-rule { margin: 1px 0; }
.ember-credit-rule { min-height: 1px; background-color: rgba(233,203,156,.17); }
.ember-credit-person, button.ember-credit-person, .ember-stage button.ember-credit-person {
  background: linear-gradient(145deg,rgba(241,214,173,.09),rgba(132,120,104,.04));
  color: #f0e2c4; border: 1px solid rgba(239,220,182,.13);
  box-shadow: inset 0 1px rgba(255,239,207,.06); border-radius: 12px;
  padding: 5px 9px 5px 6px; font-size: 13px; min-height: 0; min-width: 0; }
button.ember-credit-person:hover, .ember-stage button.ember-credit-person:hover {
  background: rgba(237,195,116,.15); border-color: rgba(246,214,164,.33); }
.ember-credit-avatar { border-radius: 50%; padding: 2px; color: #ffe2ad;
  background-image: linear-gradient(155deg,rgba(169,130,84,.46),rgba(71,55,41,.67));
  border: 1px solid rgba(248,213,152,.37); box-shadow: inset 0 1px rgba(255,238,209,.21);
  font-size: 12px; font-weight: bold; }
.ember-credit-byline { padding: 1px 0 3px; font-size: 13px; color: #f0e2c4; }
.ember-stage button.stage-credits-key, button.stage-credits-key {
  color: #e5cca1; min-height: 0; min-width: 0; padding: 3px 8px; font-size: 10px; }
.card button.widget-credits-key {
  color: #e7c695; min-width: 0; min-height: 0; padding: 3px 8px;
  border: 1px solid rgba(230,192,132,.28); border-radius: 10px;
  background: linear-gradient(to bottom,#39322a,#262421);
  box-shadow: inset 0 1px rgba(255,229,185,.13); text-shadow: none;
  font-size: 10px; }
.card button.widget-credits-key:hover, .card button.widget-credits-key:focus {
  color: #ffe3b1; border-color: rgba(241,193,122,.58);
  background: linear-gradient(to bottom,#4a3a2a,#2e2822); }
.card button.widget-credits-key:active {
  background: #221d19; box-shadow: inset 0 1px 3px rgba(0,0,0,.45); }
'''


def label(value='', style=None):
    widget = Gtk.Label(label=value, xalign=0)
    widget.set_line_wrap(True)
    widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def portrait(person, artwork, spotify_lookup):
    initials = ''.join(word[0] for word in person['name'].split() if word[0].isalnum())[:2].upper()
    monogram = Gtk.Label(label=initials or '♪')
    monogram.set_size_request(36, 36)
    stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=170)
    stack.get_style_context().add_class('ember-credit-avatar')
    stack.add_named(monogram, 'initials')
    photo = Gtk.Image()
    stack.add_named(photo, 'portrait')
    alive = True

    def destroyed(_stack):
        nonlocal alive
        alive = False

    def load(url):
        if alive and url:
            artwork.load(photo, url, 36, radius=18, on_loaded=lambda _pixels: stack.set_visible_child(photo) if alive else None)
        return False

    stack.connect('destroy', destroyed)
    stack.show_all()
    if person['image']:
        load(person['image'])
    elif spotify_lookup and person['id']:
        def resolve():
            if alive:
                GLib.idle_add(load, artist_image(person['id']))
        artwork.pool.submit(resolve)
    return stack


def group(title, participants, artwork=None, activate=None, *, grid=False, spotify=False):
    section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    section.pack_start(label(title, 'ember-credit-role'), False, False, 0)
    names = (Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=8, row_spacing=6)
             if grid else Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5))
    if grid:
        names.set_max_children_per_line(6)
    for index, person in enumerate(participants):
        name = label(person['name'], None if artwork else 'ember-credit-byline')
        if artwork:
            name.set_max_width_chars(26)
            row = Gtk.Box(spacing=9)
            row.pack_start(portrait(person, artwork, spotify and index < 4), False, False, 0)
            row.pack_start(name, True, True, 0)
            child = row
        else:
            child = name
        if activate and person['id'] and artwork:
            child = Gtk.Button()
            child.add(row)
            child.get_accessible().set_name(person['name'])
            child.connect('clicked', lambda _button, value=person: activate(value))
        if artwork:
            child.get_style_context().add_class('ember-credit-person')
        if grid:
            child.set_size_request(160, -1)
            names.add(child)
            child.get_parent().set_can_focus(False)
        else:
            names.pack_start(child, False, False, 0)
    section.pack_start(names, False, False, 0)
    return section


class TrackCredits:
    def __init__(self, host, artwork, icon=False):
        self.host = host
        self.artwork = artwork
        self.width = 292 if icon else 374
        self.caption = text('Track credits', 'О треке')
        self.button = Gtk.Button(label=text('Credits', 'О треке') if icon else self.caption)
        self.button.set_valign(Gtk.Align.CENTER)
        if icon:
            self.button.get_style_context().add_class('widget-credits-key')
        self.button.get_accessible().set_name(self.caption)
        self.button.get_style_context().add_class('stage-quiet')
        self.button.get_style_context().add_class('stage-credits-key')
        self.button.connect('clicked', self.open)
        self.popover = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='track-credits')
        self.future = None
        self.timer = 0

    def open(self, _button):
        recording = current_recording(self.host)
        if not recording:
            return
        self.dismiss()
        self.key, self.roles, apple = recording
        self.popover = popover = Gtk.Popover.new(self.button)
        popover.get_style_context().add_class('ember-credits')
        popover.set_position(Gtk.PositionType.TOP)
        sheet = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        sheet.set_size_request(self.width, -1)
        sheet.get_style_context().add_class('ember-credit-sheet')
        sheet.pack_start(label(self.caption, 'ember-credit-role'), False, False, 0)
        title = label(self.key[2], 'ember-credit-title')
        title.set_max_width_chars(30)
        sheet.pack_start(title, False, False, 0)
        rule = Gtk.Separator()
        rule.get_style_context().add_class('ember-credit-rule')
        sheet.pack_start(rule, False, False, 0)
        scroll = Gtk.ScrolledWindow(max_content_height=158 if self.width < 300 else 256,
                                    propagate_natural_height=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.add(self.rows)
        sheet.pack_start(scroll, True, True, 0)
        self.note = label(style='ember-credit-note')
        self.note.set_max_width_chars(32)
        sheet.pack_start(self.note, False, False, 0)
        popover.add(sheet)
        popover.connect('closed', lambda value: self.dismiss() if value is self.popover else None)
        sheet.show_all()
        self.render(text('Loading credits…', 'Ищем сведения об участниках…') if apple else '')
        popover.popup()
        self.timer = GLib.timeout_add(350, self.watch)
        if apple:
            self.future = self.pool.submit(apple.bridge.request, 'credits', id=self.key[1])
            self.future.add_done_callback(lambda future: GLib.idle_add(self.loaded, future))

    def render(self, status=''):
        for child in self.rows.get_children():
            child.destroy()
        titles = {'artists': text('Performers', 'Исполнители'),
                  'channel': text('YouTube channel', 'Канал YouTube'),
                  'composer': text('Composition', 'Музыка'),
                  'lyricist': text('Lyrics', 'Слова')}
        for role, title in titles.items():
            if self.roles[role]:
                artwork = self.artwork if role == 'artists' else None
                self.rows.pack_start(group(title, self.roles[role], artwork,
                                           spotify=self.key[0] == 'spotify'), False, False, 0)
        self.rows.show_all()
        if not status and not (self.roles['composer'] or self.roles['lyricist']):
            status = text('No songwriting credits from this source.', 'Источник не передал данные об авторах.')
        self.note.set_text(status)
        self.note.set_visible(bool(status))

    def watch(self):
        recording = current_recording(self.host)
        if recording and recording[0] == self.key:
            return True
        self.timer = 0
        self.dismiss()
        return False

    def loaded(self, future):
        if self.popover is None or future is not self.future or not self.watch():
            return False
        try:
            result = future.result()
        except (RuntimeError, OSError, ValueError):
            self.render(text('Credits are temporarily unavailable.', 'Сведения об авторах пока недоступны.'))
        else:
            for role in ('artists', 'composer'):
                self.roles[role] = people(result.get(role)) or self.roles[role]
            self.render()
        return False

    def dismiss(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        if self.future:
            self.future.cancel()
            self.future = None
        if self.popover:
            popover, self.popover = self.popover, None
            popover.destroy()

    def close(self):
        self.dismiss()
        self.pool.shutdown(wait=False, cancel_futures=True)
