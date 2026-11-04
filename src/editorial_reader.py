"""A warm, selectable editorial page with a reversible Russian translation."""
from gi.repository import Gtk,GLib,Pango
from source_picker import text
from listening_library import label,button
from editorial_translation import identity,is_russian

CSS=b'''
.editorial-card { background-image: linear-gradient(to bottom right,rgba(67,63,43,.64),rgba(22,30,23,.82));
  border: 1px solid rgba(239,216,166,.09); border-radius: 27px; padding: 28px 36px;
  box-shadow: inset 0 1px rgba(255,240,202,.055),0 8px 24px rgba(0,0,0,.08); }
.editorial-kicker { color: #c5a867; font-size: 9px; letter-spacing: 2.2px; }
.editorial-title { color: #f6e8c3; font-family: serif; font-weight: normal; font-size: 31px; }
.editorial-rule { background-color: rgba(229,205,155,.09); min-height: 1px; }
.editorial-body { color: #cfc5ac; font-family: sans-serif; font-size: 16px; }
.editorial-source { color: #aa9d82; font-size: 10px; }
.editorial-language { color: #dac187; font-size: 10px; padding: 4px 10px;
  background-color: rgba(12,20,15,.3); border: 1px solid rgba(231,206,148,.07); border-radius: 12px; }
.editorial-status { color: #a99e85; font-size: 10px; }
.editorial-status.editorial-error { color: #e5bf80; }
.ember-stage button.editorial-translate { background-image: linear-gradient(to bottom right,#454735,#2b3327);
  border: 1px solid rgba(232,206,151,.1); border-radius: 18px; padding: 9px 16px;
  color: #eed49a; font-size: 12px; box-shadow: inset 0 1px rgba(249,229,184,.065),0 3px 7px rgba(0,0,0,.1); }
.ember-stage button.editorial-translate:hover { border-color: rgba(244,207,126,.27); }
.ember-stage button.editorial-translate:disabled { color: #a99b79; }
.editorial-progress trough { min-height: 2px; background-color: rgba(15,23,17,.25); border: none; border-radius: 1px; }
.editorial-progress progress { min-height: 2px; background-image: linear-gradient(to right,#8d6c32,#e4bd69); border: none; border-radius: 1px; }
.ember-stage .small-screen .editorial-card { padding: 20px 22px; border-radius: 21px; }
.ember-stage .small-screen .editorial-title { font-size: 25px; }
.ember-stage .small-screen .editorial-body { font-size: 14px; }
'''


def animations():
    settings=Gtk.Settings.get_default()
    return settings is not None and settings.get_property('gtk-enable-animations')


def prose(value):
    body=label('','editorial-body');body.set_line_wrap(True)
    body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    body.set_max_width_chars(78);body.set_xalign(0);body.set_yalign(0)
    body.set_selectable(True);body.set_hexpand(True)
    # One selectable layout keeps copy/paste natural. Escape every source and
    # translated character; editorial markup is never executed.
    first,separator,rest=value.partition('\n\n')
    if len(first)>650:first,separator,rest='', '',value
    body.set_markup(('<span foreground="#f0dfb9" size="large">'+GLib.markup_escape_text(first)+'</span>'+
        (separator+GLib.markup_escape_text(rest) if separator else '')) if first else GLib.markup_escape_text(rest))
    if hasattr(Pango,'attr_line_height_new'):
        attrs=body.get_attributes() or Pango.AttrList()
        attrs.insert(Pango.attr_line_height_new(1.55));body.set_attributes(attrs)
    return body


class EditorialReader(Gtk.Box):
    def __init__(self,original,title,source,translator,album=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.original=original;self.translator=translator;self.result=None
        self.closed=False;self.loading=False;self.translated=False;self.cancel=None
        self.pulse=0;self.entrance_idle=0
        self.get_style_context().add_class('editorial-card')
        self.entrance=Gtk.Revealer();self.entrance.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.entrance.set_transition_duration(520);self.pack_start(self.entrance,False,False,0)
        column=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=17)
        column.set_halign(Gtk.Align.CENTER);column.set_hexpand(True)
        self.entrance.add(column)
        column.pack_start(label(text('THE LINER NOTES','ИСТОРИЯ АЛЬБОМА') if album else
            text('BEHIND THE MUSIC','ЗА МУЗЫКОЙ'),'editorial-kicker'),False,False,0)
        self.heading=Gtk.Box(spacing=20)
        name=label(title,'editorial-title',48);name.set_hexpand(True)
        self.heading.pack_start(name,True,True,0)
        self.translate_button=button(text('Translate to Russian','Перевести на русский'),self.toggle,'editorial-translate')
        self.translate_button.set_valign(Gtk.Align.CENTER)
        self.heading.pack_end(self.translate_button,False,False,0)
        column.pack_start(self.heading,False,False,0)
        meta=Gtk.Box(spacing=12)
        credit=label(source+'  /  '+text('Editorial','Редакционный текст'),'editorial-source',48)
        credit.set_hexpand(True);meta.pack_start(credit,True,True,0)
        self.language=label(text('Original','Оригинал'),'editorial-language')
        meta.pack_end(self.language,False,False,0);column.pack_start(meta,False,False,0)
        line=Gtk.Separator();line.get_style_context().add_class('editorial-rule');column.pack_start(line,False,False,0)
        self.pages=Gtk.Stack();self.pages.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pages.set_transition_duration(520)
        # Reserve the larger layout once the translation arrives. Crossfades
        # only composite opacity: no paragraph reflow/layout on every frame.
        self.pages.set_homogeneous(True);self.pages.set_interpolate_size(False)
        self.original_label=prose(original);self.pages.add_named(self.original_label,'original')
        column.pack_start(self.pages,False,False,0)
        self.status=label(text('Google translation · only this description is sent on request',
            'Перевод Google · по нажатию отправляется только текст описания'),'editorial-status')
        self.status.set_line_wrap(True);self.status.set_max_width_chars(90)
        column.pack_start(self.status,False,False,0)
        self.progress=Gtk.ProgressBar();self.progress.get_style_context().add_class('editorial-progress')
        self.progress.set_no_show_all(True);self.progress.set_pulse_step(.025)
        column.pack_start(self.progress,False,False,0)
        self.connect('map',self.mapped);self.connect('unmap',self.unmapped)
        self.connect('destroy',self.destroyed);self.connect('size-allocate',self.resize)
        if is_russian(original):
            self.language.set_text(text('Russian','Русский'))
            self.translate_button.set_label(text('Already in Russian','Уже на русском'));self.translate_button.set_sensitive(False)
            self.status.set_text(text('Original text supplied by the music service','Оригинальный текст музыкального сервиса'))
        elif identity(original) in translator.preferred:
            self.begin_translation()

    def resize(self,_widget,allocation):
        orientation=Gtk.Orientation.VERTICAL if allocation.width<640 else Gtk.Orientation.HORIZONTAL
        if self.heading.get_orientation()!=orientation:
            self.heading.set_orientation(orientation)
            self.translate_button.set_halign(Gtk.Align.START if allocation.width<640 else Gtk.Align.FILL)

    def mapped(self,*_args):
        self.entrance.set_transition_duration(520 if animations() else 0)
        if not self.entrance_idle:self.entrance_idle=GLib.idle_add(self.reveal)
        if self.loading:self.start_pulse()

    def reveal(self):
        self.entrance_idle=0
        if not self.closed and self.get_mapped():self.entrance.set_reveal_child(True)
        return False

    def unmapped(self,*_args):
        self.stop_pulse()
        if self.entrance_idle:GLib.source_remove(self.entrance_idle);self.entrance_idle=0
        self.entrance.set_transition_duration(0);self.entrance.set_reveal_child(False)

    def toggle(self):
        if self.closed or self.loading:return
        if not self.result:self.begin_translation();return
        self.translated=not self.translated
        self.translator.prefer(self.original,self.translated);self.show_language()

    def begin_translation(self):
        self.loading=True;self.translate_button.set_sensitive(False)
        self.translate_button.set_label(text('Translating…','Перевожу…'))
        self.status.get_style_context().remove_class('editorial-error')
        self.status.set_text(text('Preparing a Russian version. The original stays here.',
            'Готовлю русский текст. Оригинал остаётся доступен.'))
        self.progress.show();self.start_pulse()
        self.cancel=self.translator.request(self.original,self.completed)

    def start_pulse(self):
        if self.pulse or not self.get_mapped() or not animations():return
        def advance():
            if self.closed or not self.loading or not self.get_mapped() or not animations():self.pulse=0;return False
            self.progress.pulse();return True
        self.pulse=GLib.timeout_add(80,advance)

    def stop_pulse(self):
        if self.pulse:GLib.source_remove(self.pulse);self.pulse=0

    def completed(self,result,error):
        if self.closed:return
        self.loading=False;self.cancel=None;self.stop_pulse();self.progress.hide()
        self.translate_button.set_sensitive(True)
        if error:
            self.translator.prefer(self.original,False)
            self.translate_button.set_label(text('Retry translation','Повторить перевод'))
            self.status.set_text(text('Translation is temporarily unavailable. The original is intact.',
                'Перевод временно недоступен. Оригинал сохранён — можно повторить.'))
            self.status.get_style_context().add_class('editorial-error');return
        self.result=result;self.translated=True
        self.russian_label=prose(result);self.pages.add_named(self.russian_label,'russian');self.russian_label.show()
        self.show_language()

    def show_language(self):
        self.pages.set_transition_duration(520 if animations() and self.get_mapped() else 0)
        self.pages.set_visible_child_name('russian' if self.translated else 'original')
        self.language.set_text(text('Russian','Русский') if self.translated else text('Original','Оригинал'))
        self.translate_button.set_label(text('Show original','Показать оригинал') if self.translated else text('Read in Russian','Читать на русском'))
        self.status.set_text(text('Automatic translation · Google · the original is one click away',
            'Автоматический перевод · Google · оригинал доступен по кнопке') if self.translated else
            text('Original text · Russian translation saved on this device','Оригинальный текст · русский перевод сохранён на устройстве'))

    def destroyed(self,*_args):
        self.closed=True;self.unmapped()
        if self.cancel:self.cancel();self.cancel=None
