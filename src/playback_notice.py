"""Honest loading stages for the desktop player; no estimated percentages."""
from dataclasses import dataclass
import time
from gi.repository import Gtk, Pango
from source_picker import text


CSS=b'''
.playback-notice { background-color: rgba(36,37,32,.97); border-radius: 13px;
  border: 1px solid rgba(250,189,47,.15); padding: 5px 9px;
  box-shadow: inset 1px 1px 3px rgba(0,0,0,.45), inset -1px -1px 2px rgba(255,241,199,.04); }
.playback-notice label { color: #e3c98c; font-size: 10px; }
.playback-notice spinner { color: #fabd2f; min-width: 13px; min-height: 13px; }
.playback-notice.error label { color: #e6a879; }
.playback-notice.header-notice { padding: 3px 6px; border-radius: 11px; }
.playback-notice button { background: transparent; border: none; box-shadow: none;
  color: #fabd2f; padding: 0 2px; min-width: 16px; min-height: 16px; }
'''


@dataclass(frozen=True)
class Notice:
    phase: str=''
    message: str=''
    busy: bool=False
    action: str=''


def playback_notice(host):
    source=host.source
    name={'spotify':'Spotify','apple-music':'Apple Music','yandex-music':text('Yandex Music','Яндекс Музыка'),'youtube':'YouTube'}.get(source,'Ember')
    music=getattr(host,'music',None)
    client=getattr(host,'native_web',lambda:None)()
    state=getattr(client,'state',{}) or {};spatial=state.get('spatial') or {}
    youtube=getattr(host,'youtube',None) if source=='youtube' and getattr(host,'youtube_native',lambda:False)() else None
    error=getattr(music,'error','') or getattr(client,'error','') or getattr(youtube,'error','')
    if not error and spatial.get('error'):error=text('Audio preparation failed · retry','Не удалось подготовить звук · повторить')
    if error:
        return Notice('error',str(error),False,'track' if getattr(music,'error','') else 'retry')
    if getattr(music,'loading',False) or getattr(youtube,'loading',False) or spatial.get('switching') or spatial.get('phase')=='preparing':
        message=text('Loading your track…','Загружаю трек…')
        if source=='apple-music' and spatial.get('enabled') and spatial.get('phase')=='preparing':
            message=text('Preparing high-quality audio…','Готовлю звук высокого качества…')
        return Notice('track',message,True)
    if spatial.get('seeking'):
        return Notice('seek',text('Seeking…','Перематываю…'),True)
    if client:
        if getattr(client,'upgrading',False):return Notice('upgrade',text('Updating the music engine…','Обновляю музыкальный движок…'),True)
        if getattr(client,'spatial_preparing',False):return Notice('audio',text('Preparing audio…','Подготавливаю звук…'),True)
        if not client.connected or getattr(client,'starting',False):
            return Notice('connect',text('Connecting ','Подключаю ')+name+'…',True)
        if not state.get('ready'):
            return Notice('service',text('Loading ','Загружаю ')+name+'…',True)
        if state.get('authorized') is False:
            return Notice('signin',text('Sign in to ','Войди в ')+name,False,'accounts')
    if not getattr(getattr(host,'equalizer',None),'frames_ready',True):
        return Notice('lamps',text('Preparing the warm glow…','Подготавливаю лампы…'),True)
    if getattr(host,'startup_pending',False):
        return Notice('startup',text('Restoring your music…','Восстанавливаю состояние плеера…'),True)
    return Notice()


class PlaybackNotice(Gtk.EventBox):
    def __init__(self,host):
        super().__init__();self.host=host;self.key=None;self.since=0.;self.action='';self.busy=False
        self.set_visible_window(False);self.set_no_show_all(True)
        self.set_halign(Gtk.Align.END);self.set_valign(Gtk.Align.START)
        row=Gtk.Box(spacing=7);self.add(row)
        self.notice_context=row.get_style_context();self.notice_context.add_class('playback-notice')
        self.notice_context.add_class('header-notice')
        self.spinner=Gtk.Spinner();row.pack_start(self.spinner,False,False,0)
        self.label=Gtk.Label();self.label.set_xalign(0);self.label.set_hexpand(True);self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_max_width_chars(16)
        row.pack_start(self.label,True,True,0)
        self.retry=Gtk.Button();icon=Gtk.Image.new_from_icon_name('view-refresh-symbolic',Gtk.IconSize.MENU)
        icon.set_pixel_size(13);self.retry.add(icon);row.pack_end(self.retry,False,False,0)
        self.retry.connect('clicked',self.activate)
        self.connect('map',lambda *_:self.sync_spinner())
        self.connect('unmap',lambda *_:self.spinner.stop())
        row.show_all();self.hide()

    def sync_spinner(self):
        if self.busy and self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):self.spinner.start()
        else:self.spinner.stop()

    def update(self,show=True):
        value=playback_notice(self.host);music=getattr(self.host,'music',None)
        key=(self.host.source,value.phase,getattr(music,'play_generation',0))
        now=time.monotonic()
        if key!=self.key:self.key=key;self.since=now
        message=value.message;self.action=value.action;self.busy=value.busy
        if value.busy:
            message={'connect':text('Connecting…','Подключаю…'),'service':text('Loading library…','Медиатека…'),
                     'track':text('Loading track…','Загружаю трек…'),'audio':text('Preparing audio…','Готовлю звук…'),
                     'lamps':text('Preparing lamps…','Готовлю лампы…'),'startup':text('Starting…','Запускаю…'),
                     'upgrade':text('Updating…','Обновляю…')}.get(value.phase,message)
        if self.busy and now-self.since>12:
            message=text('Still loading · retry is available','Загрузка продолжается · можно повторить')
            book=getattr(music,'book',None)
            self.action='track' if value.phase=='track' and book and book.current(self.host.source) else 'retry'
        if self.busy and now-self.since>30:
            message=text('Taking too long · reconnect','Долгое ожидание · обновить соединение')
            self.busy=False
        context=self.notice_context
        context.add_class('error') if message and not self.busy else context.remove_class('error')
        if self.label.get_text()!=message:self.label.set_text(message)
        self.get_accessible().set_name(value.message if self.busy else message)
        self.retry.get_accessible().set_name(text('Sign in','Войти') if self.action=='accounts' else text('Retry','Повторить'))
        self.retry.set_visible(bool(self.action));self.spinner.set_visible(self.busy)
        self.set_visible(bool(message) and show);self.sync_spinner()

    def activate(self,*_):
        self.key=None
        if self.action=='accounts':self.host.show_accounts(self.host.source)
        elif self.action=='track':
            music=self.host.music;music.start(music.book.indices[self.host.source])
        else:self.host.reconnect_player()
