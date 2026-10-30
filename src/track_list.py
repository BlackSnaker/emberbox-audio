"""Readable record lists with independent play, artist and queue controls."""
from gi.repository import Gtk,Pango
from source_picker import text
from listening_queue import track,matches


CSS=b'''
.record-panel { background-color: rgba(12,20,17,.28); border: 1px solid rgba(235,219,178,.065);
  border-radius: 19px; padding: 5px 7px 7px; box-shadow: inset 0 1px rgba(251,241,199,.025); }
.record-header { padding: 10px 14px 12px; border-bottom: 1px solid rgba(235,219,178,.065); }
.record-heading { color: #a5a58e; font-family: 'Noto Sans'; font-size: 10px; letter-spacing: 1.2px; }
.record-list { background: transparent; border: none; padding: 4px 0 0; }
.record-list row.record-row { background: transparent; border: 1px solid transparent;
  border-radius: 12px; padding: 8px 12px; outline: none; box-shadow: none;
  transition-property: background-color, border-color; transition-duration: 180ms; }
.record-list row.record-row:hover, .record-list row.record-row:focus {
  background-color: rgba(235,219,178,.045); border-color: rgba(235,219,178,.055); }
.record-list row.record-row.record-current {
  background-color: rgba(222,177,74,.075); border-color: rgba(239,193,94,.15);
  box-shadow: inset 2px 0 rgba(239,193,94,.72); }
.record-list row.record-row.record-pending { border-color: rgba(239,193,94,.12); }
.record-rank { font-family: 'Noto Sans Mono'; font-size: 11px; color: #8f9784; }
.record-indicator { color: #edc575; }
.ember-stage button.record-title, .ember-stage button.record-artist {
  background: transparent; border: none; box-shadow: none; padding: 0; min-width: 0; min-height: 0;
  border-radius: 4px; outline: none; }
.record-title label { color: #f3e9c9; font-family: 'Noto Sans'; font-size: 16px; font-weight: 600;
  letter-spacing: 0; transition-property: color; transition-duration: 160ms; }
.record-current .record-title label { color: #f4d48a; }
.record-artist label, label.record-artist { color: #b7b7a3; font-family: 'Noto Sans'; font-size: 13px;
  font-weight: normal; letter-spacing: 0; transition-property: color; transition-duration: 160ms; }
.record-title:hover label, .record-artist:hover label { color: #ffe3a5; }
.record-album { color: #b2b29c; font-family: 'Noto Sans'; font-size: 13px; font-weight: normal; }
.record-duration { color: #b9b29b; font-family: 'Noto Sans Mono'; font-size: 12px; }
.ember-stage button.record-action { background-image: linear-gradient(to bottom right,rgba(71,76,53,.5),rgba(32,41,30,.7));
  color: #d9cfad; border: 1px solid rgba(235,219,178,.06); border-radius: 12px; padding: 0;
  min-width: 32px; min-height: 32px; box-shadow: inset 0 1px rgba(251,241,199,.03);
  transition-property: background-color, border-color, color; transition-duration: 160ms; }
.ember-stage button.record-action:hover { color: #f8d18a; border-color: rgba(235,193,99,.25);
  background-color: rgba(215,153,33,.08); }
.ember-stage button.record-action:active { box-shadow: inset 1px 2px 4px rgba(0,0,0,.22); }
.ember-stage button.record-action:disabled { color: #646e5b; background-image: none; border-color: transparent; }
.record-row:disabled .record-title label, .record-row:disabled .record-artist label { color: #75806e; }
.record-title:disabled label { color: #75806e; }
.record-compact .record-title label { font-size: 14px; }
.record-compact .record-artist label, .record-compact label.record-artist { font-size: 12px; }
'''


def ellipsis(value,style):
    label=Gtk.Label(label=str(value or ''));label.set_xalign(0)
    label.set_ellipsize(Pango.EllipsizeMode.END);label.set_width_chars(1)
    label.set_max_width_chars(1);label.set_hexpand(True)
    label.get_style_context().add_class(style)
    return label


def action(icon,name,callback):
    button=Gtk.Button();image=Gtk.Image.new_from_icon_name(icon,Gtk.IconSize.MENU)
    image.set_pixel_size(14);button.add(image)
    button.set_valign(Gtk.Align.CENTER);button.set_has_tooltip(False)
    button.get_style_context().add_class('record-action')
    button.get_accessible().set_name(name);button.connect('clicked',lambda _b:callback())
    return button


def fixed(widget,width):
    widget.set_size_request(width,-1)
    widget.set_valign(Gtk.Align.CENTER)
    return widget


class RecordRow(Gtk.ListBoxRow):
    def __init__(self,item,index,source,artwork,play,artist,actions,*,show_art=True):
        super().__init__()
        self.item=item;self.record=track(item,source);self.index=index;self.play=play;self.display_state=None
        self.get_style_context().add_class('record-row')
        self.set_activatable(bool(self.record));self.set_selectable(False)
        self.get_accessible().set_name(item.get('title','')+' · '+item.get('artist',''))
        box=Gtk.Box(spacing=14);self.add(box)
        self.rank=Gtk.Stack();self.rank.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.rank.set_transition_duration(160);fixed(self.rank,28)
        number=Gtk.Label(label=f'{index+1:02}');number.get_style_context().add_class('record-rank')
        self.rank.add_named(number,'number')
        self.indicator=Gtk.Image.new_from_icon_name('media-playback-start-symbolic',Gtk.IconSize.MENU)
        self.indicator.set_pixel_size(12);self.indicator.get_style_context().add_class('record-indicator')
        self.rank.add_named(self.indicator,'current')
        waiting=Gtk.Label(label='···');waiting.get_style_context().add_class('record-indicator')
        self.rank.add_named(waiting,'pending');box.pack_start(self.rank,False,False,0)
        self.image=Gtk.Image();fixed(self.image,48);self.image.set_no_show_all(not show_art)
        if show_art:artwork.load(self.image,item.get('image',''),48,9)
        box.pack_start(self.image,False,False,0)
        names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);names.set_valign(Gtk.Align.CENTER)
        names.set_hexpand(True)
        self.play_button=Gtk.Button();self.play_button.set_has_tooltip(False)
        self.play_button.set_can_focus(False);self.play_button.get_style_context().add_class('record-title')
        self.name=ellipsis(item.get('title',''),'record-title')
        self.play_button.add(self.name);self.play_button.set_sensitive(bool(self.record))
        self.play_button.get_accessible().set_name(text('Play: ','Слушать: ')+item.get('title',''))
        self.play_button.connect('clicked',lambda _b:play())
        names.pack_start(self.play_button,False,False,0)
        self.artist_label=ellipsis(item.get('artist') or item.get('subtitle',''),'record-artist')
        self.artist_button=None
        if artist and item.get('artist'):
            self.artist_button=Gtk.Button();self.artist_button.set_has_tooltip(False)
            self.artist_button.set_halign(Gtk.Align.START);self.artist_label.set_max_width_chars(64)
            self.artist_button.get_style_context().add_class('record-artist')
            self.artist_button.get_accessible().set_name(text('Open artist: ','Открыть артиста: ')+item['artist'])
            self.artist_button.add(self.artist_label);self.artist_button.connect('clicked',lambda _b:artist())
            names.pack_start(self.artist_button,False,False,0)
        else:names.pack_start(self.artist_label,False,False,0)
        box.pack_start(names,True,True,0)
        self.album=ellipsis(item.get('album') or '—','record-album');self.album.set_no_show_all(True)
        self.album.set_hexpand(False)
        box.pack_start(self.album,False,False,0)
        seconds=int(item.get('duration_ms') or 0)//1000
        self.duration=Gtk.Label(label=f'{seconds//60}:{seconds%60:02d}' if seconds else '—')
        self.duration.set_xalign(1);self.duration.get_style_context().add_class('record-duration')
        box.pack_start(fixed(self.duration,60),False,False,0)
        self.actions=Gtk.Box(spacing=6);self.actions.set_valign(Gtk.Align.CENTER)
        self.action_buttons=[]
        for icon,name,callback,enabled in actions:
            b=action(icon,name,callback);b.set_sensitive(enabled)
            self.actions.pack_start(b,False,False,0);self.action_buttons.append(b)
        box.pack_end(self.actions,False,False,0)
        self.show_all();self.album.hide()

    def state(self,current,playing,pending=False):
        key=(current,playing if current else False,pending)
        if key==self.display_state:return
        self.display_state=key
        style=self.get_style_context()
        for name,enabled in (('record-current',current),('record-pending',pending)):
            style.add_class(name) if enabled else style.remove_class(name)
        if current:self.indicator.set_from_icon_name('media-playback-start-symbolic' if playing else 'media-playback-pause-symbolic',Gtk.IconSize.MENU)
        self.rank.set_visible_child_name('pending' if pending else 'current' if current else 'number')
        self.get_accessible().set_description(text('Starting track','Трек загружается') if pending else text('Now playing','Сейчас играет') if current and playing else text('Current track · paused','Текущий трек · пауза') if current else '')


class RecordList(Gtk.Box):
    def __init__(self,action_count=1,*,album=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class('record-panel')
        self.rows=[];self.layout_key=None;self.album_mode=album
        if album:self.get_style_context().add_class('album-records')
        self.header=Gtk.Box(spacing=14);self.header.get_style_context().add_class('record-header')
        number=Gtk.Label(label='#');number.get_style_context().add_class('record-heading')
        self.header.pack_start(fixed(number,28),False,False,0)
        self.art_heading=fixed(Gtk.Label(),48);self.art_heading.set_no_show_all(album)
        self.header.pack_start(self.art_heading,False,False,0)
        title=ellipsis(text('RECORDING','КОМПОЗИЦИЯ'),'record-heading')
        self.header.pack_start(title,True,True,0)
        self.album_heading=ellipsis(text('ALBUM','АЛЬБОМ'),'record-heading');self.album_heading.set_no_show_all(True)
        self.album_heading.set_hexpand(False)
        self.header.pack_start(self.album_heading,False,False,0)
        time=Gtk.Label(label=text('TIME','ВРЕМЯ'));time.set_xalign(1);time.get_style_context().add_class('record-heading')
        self.header.pack_start(fixed(time,60),False,False,0)
        self.header.pack_end(fixed(Gtk.Label(),34*action_count+6*(action_count-1)),False,False,0)
        self.pack_start(self.header,False,False,0)
        self.list=Gtk.ListBox();self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.set_activate_on_single_click(True);self.list.get_style_context().add_class('record-list')
        self.list.connect('row-activated',lambda _list,row:row.play() if row.record else None)
        self.pack_start(self.list,False,False,0)

    def append(self,row):self.rows.append(row);self.list.add(row)

    def resize(self,width):
        key=(not self.album_mode and width>=1120,width<1000,max(200,min(340,round(width*.23))))
        if key==self.layout_key:return
        self.layout_key=key;album,compact,size=key
        context=self.get_style_context()
        context.add_class('record-compact') if compact else context.remove_class('record-compact')
        for widget in [self.album_heading]+[row.album for row in self.rows]:
            widget.set_size_request(size,-1);widget.set_visible(album)

    def set_state(self,state,pending=None):
        for row in self.rows:
            current=bool(row.record and state.get('valid') and matches(row.record,state))
            starting=bool(row.record and pending and matches(row.record,pending))
            row.state(current,bool(state.get('playing')),starting)
