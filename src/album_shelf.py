"""The collection's record cabinet, sleeve and physical-edition card."""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache
import hashlib
from pathlib import Path

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from album_shelf_data import AlbumWishlist, edition_links, release_reference
from cover_pause_paint import bindings, gradient, rounded
from record_inspector import CSS as INSPECTOR_CSS, INSPECT_ART_SIZE, RecordInspector, keyboard_click
from source_picker import text


CSS = b'''
.record-cabinet { border-radius: 21px; border: 1px solid #58422f; background-color: #25180e; }
.record-plaque { padding: 8px 18px; border: 1px solid rgba(235,174,103,.61); border-radius: 12px;
  background-image: linear-gradient(140deg,#31231a,#15100e 65%,#352315);
  box-shadow: inset 0 1px rgba(251,209,141,.24), 0 5px 17px rgba(0,0,0,.35); }
.record-plaque-title { color: #edc28b; font-weight: bold; font-size: 15px; }
.record-muted { color: #ddbb95; font-size: 11px; }
.record-detail { padding: 12px; border-radius: 20px; border: 1px solid rgba(228,180,120,.23);
  background-image: linear-gradient(144deg,#29211a,#161411 65%,#242018);
  box-shadow: inset 0 1px rgba(249,203,144,.12); }
.record-detail-title { color: #f7e7cb; font-size: 21px; font-weight: bold; }
.record-shelf-status { padding: 22px 28px; }
.record-format-label { color: #e3b57c; font-size: 11px; font-weight: bold; }
.record-detail-scroll, .record-detail-scroll viewport { background-color: transparent; border: none; }
.ember-stage button.record-spine, .ember-stage button.record-spine:hover,
.ember-stage button.record-spine:active, .ember-stage button.record-inspect-sleeve:hover,
.ember-stage button.record-inspect-sleeve:active {
  min-width: 0; min-height: 0; padding: 0; border: none; border-radius: 4px;
  background: transparent; box-shadow: none; }
.ember-stage button.record-spine:focus {
  outline: 1px solid #ffe1ad; outline-offset: -1px; }
.record-spine label { color: #f2dfc1; font-size: 10px; font-weight: bold;
  text-shadow: 0 1px rgba(0,0,0,.75); }
.record-spine:hover label, .record-spine.selected-spine label { color: #fff2d8; }
.ember-stage button.record-plaque-key, .ember-stage combobox.record-format button {
  color: #f4d7af; font-size: 12px; background-image: linear-gradient(to bottom,#34271d,#201913);
  border: 1px solid rgba(235,174,103,.32); border-radius: 11px;
  box-shadow: inset 0 1px rgba(247,205,142,.13); }
.ember-stage button.record-plaque-key:hover, .ember-stage combobox.record-format button:hover {
  background-image: linear-gradient(to bottom,#4c3626,#271d16); }
.record-shelf-dense .record-detail { padding: 7px 11px; }
.record-shelf-dense .record-detail-title { font-size: 17px; }
.record-detail-scroll scrollbar, .record-detail-scroll scrollbar trough {
  background: #231a14; border: none; box-shadow: none; }
.record-detail-scroll scrollbar slider { min-width: 4px; border-radius: 4px;
  background-color: rgba(206,164,116,.43); }
'''+INSPECTOR_CSS


def caption(value, style, wrap=False):
    label = Gtk.Label(label=value, xalign=0)
    label.get_style_context().add_class(style)
    if wrap:
        label.set_width_chars(1)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return label


def key(value, callback, style='stage-quiet'):
    button = Gtk.Button(label=value)
    button.get_style_context().add_class(style)
    button.connect('clicked', lambda *_: callback())
    return button


def cabinet_geometry(width, height):
    """Keep the photographed objects proportional at all window ratios."""
    scene_height = min(height, width * (2/3))
    return (height-scene_height)/2, scene_height


@lru_cache(maxsize=1)
def pixbuf_cairo():
    gdk = C.CDLL(find_library('gdk-3'))
    gdk.gdk_cairo_set_source_pixbuf.argtypes = [C.c_void_p,C.c_void_p,C.c_double,C.c_double]
    gdk.gdk_cairo_set_source_pixbuf.restype = None
    return gdk


class ShelfDrawing(Gtk.DrawingArea):
    def __init__(self, paint):
        super().__init__()
        self.c, signals, self.pointer = bindings()
        self.gdk = pixbuf_cairo()
        self.draw_callback = C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(
            lambda _widget,cr,_data: paint(cr) or False)
        pointer = self.pointer(self.__gpointer__,None)
        handler = signals.g_signal_connect_data(pointer,b'draw',self.draw_callback,None,None,0)
        self.connect('destroy',lambda *_:signals.g_signal_handler_disconnect(pointer,handler))

    def paint_pixbuf(self, cr, pixels, x, y, width, height):
        c = self.c
        c.cairo_save(cr)
        c.cairo_translate(cr,x,y)
        c.cairo_scale(cr,width/pixels.get_width(),height/pixels.get_height())
        self.gdk.gdk_cairo_set_source_pixbuf(cr,self.pointer(pixels.__gpointer__,None),0,0)
        c.cairo_pattern_set_filter(c.cairo_get_source(cr),4)
        c.cairo_paint(cr)
        c.cairo_restore(cr)


SPINE_COLORS = (
    (.52,.25,.18), (.28,.40,.32), (.56,.36,.19),
    (.39,.28,.40), (.24,.37,.49), (.45,.43,.25),
)


class SpinePrint(ShelfDrawing):
    def __init__(self, color, side, face):
        super().__init__(self.paint)
        self.color, self.side, self.face = color, side, face
        self.art = None
        self.selected = self.highlighted = False

    def set_art(self, pixels):
        if pixels is None:
            return
        self.art = pixels
        raw = pixels.get_pixels()
        channels, stride = pixels.get_n_channels(), pixels.get_rowstride()
        xs = (pixels.get_width()//5, pixels.get_width()//2, 4*pixels.get_width()//5)
        ys = (pixels.get_height()//5, pixels.get_height()//2, 4*pixels.get_height()//5)
        samples = [raw[y*stride+x*channels:y*stride+x*channels+3] for y in ys for x in xs]
        self.color = tuple(.13 + .45*sum(sample[i] for sample in samples)/2300 for i in range(3))
        self.queue_draw()

    def paint(self, cr):
        c = self.c
        w, h = self.get_allocated_width(), self.get_allocated_height()
        if w < 10 or h < 45:
            return False
        y = 3 if self.selected else 2 if self.highlighted else 9
        x, width, height = 1., w-2., h-6-y
        warm = 1. if self.highlighted else .62 if self.selected else .35
        spine = 19 if self.face else width
        face = width-spine
        edge = x+face if self.side < 0 else x
        print_x = x if self.side < 0 else x+spine
        red, green, blue = self.color
        shadow = gradient(c,0,h-9,0,h,((0,.06,.025,.009,0),(.56,.06,.025,.009,.75),(1,.06,.025,.009,0)))
        c.cairo_rectangle(cr,0,h-9,w,9)
        c.cairo_set_source(cr,shadow);c.cairo_fill(cr);c.cairo_pattern_destroy(shadow)
        c.cairo_save(cr)
        rounded(c,cr,x,y,width,height,2.8);c.cairo_clip(cr)
        c.cairo_set_source_rgba(cr,red*.42,green*.42,blue*.42,1.);c.cairo_paint(cr)
        if self.face and self.art:
            c.cairo_save(cr)
            c.cairo_rectangle(cr,print_x,y,face,height);c.cairo_clip(cr)
            image_width = height*self.art.get_width()/self.art.get_height()
            visible_edge = .70 if self.side < 0 else .30
            self.paint_pixbuf(cr,self.art,print_x-(image_width-face)*visible_edge,y,image_width,height)
            c.cairo_restore(cr)
        jacket = gradient(c,edge,0,edge+spine,0,(
            (0,.07,.045,.033,1),(.13,red*.92,green*.92,blue*.92,1),
            (.35,red*.72,green*.72,blue*.72,1),(.73,red*.82,green*.82,blue*.82,1),
            (.94,red*.52,green*.52,blue*.52,1),(1,.06,.042,.031,1)))
        c.cairo_rectangle(cr,edge,y,spine,height)
        c.cairo_set_source(cr,jacket);c.cairo_fill(cr);c.cairo_pattern_destroy(jacket)
        sheen = gradient(c,0,y,0,y+height,(
            (0,1,.79,.52,.35*warm),(.16,1,.77,.51,.09*warm),(.55,.05,.027,.014,.04),
            (.90,.05,.027,.014,.19),(1,.04,.02,.01,.49)))
        c.cairo_set_source(cr,sheen);c.cairo_paint(cr);c.cairo_pattern_destroy(sheen)
        # Ink bands and folded paper catch the shelf lamp along the edges.
        c.cairo_set_source_rgba(cr,.99,.76,.48,.26+.25*warm)
        for line in (y+8,y+height-16,y+height-13):
            c.cairo_rectangle(cr,edge+3,line,max(10.,spine-6),.75)
        c.cairo_rectangle(cr,x,y,width,1)
        c.cairo_rectangle(cr,x,y+1,1,height-2)
        c.cairo_fill(cr)
        c.cairo_set_source_rgba(cr,.02,.014,.01,.66)
        c.cairo_rectangle(cr,x+width-1,y,1,height)
        c.cairo_rectangle(cr,x,y+height-1,width,1)
        c.cairo_fill(cr)
        c.cairo_restore(cr)
        return False


class RecordSpine(Gtk.Button):
    def __init__(self, release, width, height, side, front, artwork, choose):
        super().__init__()
        self.get_style_context().add_class('record-spine')
        self.set_valign(Gtk.Align.END)
        self.get_accessible().set_name(release['title'])
        self.get_accessible().set_description(release.get('artist',''))
        seed = hashlib.blake2s(release['uri'].encode(),digest_size=2).digest()
        self.print = SpinePrint(SPINE_COLORS[seed[0]%len(SPINE_COLORS)],side,front)
        self.print.set_size_request(width,height-seed[1]%11)
        surface = Gtk.Overlay()
        surface.add(self.print)
        title = Gtk.Label(label=release['title'],angle=90,halign=Gtk.Align.CENTER,valign=Gtk.Align.CENTER)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(max(6,min(24,(height-32)//7)))
        if front:
            shift = (width-20)//2
            (title.set_margin_start if side < 0 else title.set_margin_end)(shift*2)
        surface.add_overlay(title)
        surface.set_overlay_pass_through(title,True)
        self.add(surface)
        self.connect('clicked',lambda *_:choose(release,animate=True))
        self.connect('state-flags-changed',self.update_highlight)
        if front and release.get('image'):
            photo = Gtk.Image()
            self.connect('destroy',lambda *_:photo.destroy())
            artwork.load(photo,release['image'],320,0,high_quality=True,keep_aspect=True,
                         on_loaded=self.print.set_art)

    def update_highlight(self, *_):
        flags = Gtk.StateFlags.PRELIGHT | Gtk.StateFlags.FOCUSED
        highlighted = bool(self.get_state_flags() & flags)
        if self.print.highlighted != highlighted:
            self.print.highlighted = highlighted
            self.print.queue_draw()

    def set_selected(self, selected):
        if self.print.selected == selected:
            return
        self.print.selected = selected
        style = self.get_style_context()
        (style.add_class if selected else style.remove_class)('selected-spine')
        self.print.queue_draw()


class Sleeve(ShelfDrawing):
    def __init__(self):
        super().__init__(self.paint)
        self.art = None
        self.highlighted = False
        self.started = 0
        self.tick = 0
        self.amount = 1.
        self.connect('unmap', lambda *_: self.finish())

    def finish(self):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.amount = 1.

    def pull(self):
        self.finish()
        if self.get_mapped() and Gtk.Settings.get_default().get_property('gtk-enable-animations'):
            self.started = GLib.get_monotonic_time()
            self.amount = 0.
            self.tick = self.add_tick_callback(self.animate)
        self.queue_draw()

    def animate(self, _widget, clock):
        progress = max(0., min(1., (clock.get_frame_time()-self.started)/380000))
        self.amount = 1-(1-progress)**3
        self.queue_draw()
        if progress >= 1:
            self.tick = 0
            return False
        return True

    def highlight(self, button, *_):
        flags = Gtk.StateFlags.PRELIGHT | Gtk.StateFlags.FOCUSED
        highlighted = bool(button.get_state_flags() & flags)
        if self.highlighted != highlighted:
            self.highlighted = highlighted
            self.queue_draw()

    def paint(self, cr):
        if self.art is None:
            return False
        width, height = self.get_allocated_width(), self.get_allocated_height()
        size = min(height*.87,width*.85)
        if size < 10:
            return False
        c = self.c
        half = size/2
        x = width*.5
        y = height-half-13.+(1-self.amount)*min(16.,size*.07)
        shadow = c.cairo_pattern_create_radial(0,0,.08,0,0,1)
        for stop in ((0,.095,.040,.013,.86),(.55,.072,.032,.011,.65),(1,.072,.032,.011,0)):
            c.cairo_pattern_add_color_stop_rgba(shadow,*stop)
        c.cairo_save(cr)
        c.cairo_translate(cr,x+4,height-5)
        c.cairo_scale(cr,size*.54,max(3.,size*.037))
        c.cairo_set_source(cr,shadow);c.cairo_paint(cr)
        c.cairo_restore(cr);c.cairo_pattern_destroy(shadow)
        c.cairo_save(cr)
        c.cairo_translate(cr,x+(1-self.amount)*min(12.,size*.04),y)
        c.cairo_rotate(cr,-.091*self.amount)
        cover_edge = gradient(c,-half,-half,half,half,(
            (0,.65,.39,.18,1),(.20,.28,.16,.091,1),(.44,.10,.070,.052,1),
            (.68,.12,.082,.054,1),(.88,.43,.24,.12,1),(1,.12,.063,.029,1)))
        rounded(c,cr,-half-5,-half-2,size+11,size+9,5)
        c.cairo_set_source_rgba(cr,.04,.021,.010,.90);c.cairo_fill(cr)
        rounded(c,cr,-half-3,-half-2,size+7,size+5,3.5)
        c.cairo_set_source(cr,cover_edge);c.cairo_fill(cr);c.cairo_pattern_destroy(cover_edge)
        c.cairo_save(cr)
        rounded(c,cr,-half,-half,size,size,2.5);c.cairo_clip(cr)
        c.cairo_set_source_rgba(cr,.07,.044,.029,1.);c.cairo_paint(cr)
        scale = min(size/self.art.get_width(),size/self.art.get_height())
        print_width, print_height = self.art.get_width()*scale,self.art.get_height()*scale
        self.paint_pixbuf(cr,self.art,-print_width*.5,-print_height*.5,print_width,print_height)
        reflected = gradient(c,-half,-half,half,half,(
            (0,1,.84,.63,.35 if self.highlighted else .24),
            (.14,1,.83,.60,.12 if self.highlighted else .08),(.46,1,.80,.52,0),
            (.80,.06,.035,.020,0),(1,.06,.035,.020,.18)))
        c.cairo_set_source(cr,reflected);c.cairo_paint(cr);c.cairo_pattern_destroy(reflected)
        c.cairo_restore(cr)
        rounded(c,cr,-half,-half,size,size,2.5)
        c.cairo_set_source_rgba(cr,1,.78,.49,.88 if self.highlighted else .56)
        c.cairo_set_line_width(cr,.85);c.cairo_stroke(cr)
        c.cairo_set_source_rgba(cr,1,.86,.65,.40)
        c.cairo_rectangle(cr,-half-1.8,-half+4,.8,size-7)
        c.cairo_rectangle(cr,-half+3,-half-1.6,size-7,.8)
        c.cairo_fill(cr)
        c.cairo_restore(cr)
        return False


class AlbumShelf(Gtk.Box):
    def __init__(self, artwork, wishlist_path, details, play, load_more, retry):
        super().__init__(spacing=13)
        self.artwork = artwork
        self.wishlist = AlbumWishlist(wishlist_path)
        self.details, self.play, self.load_more = details, play, load_more
        self.source = ''
        self.albums, self.items, self.spines = [], [], []
        self.capacity, self.page = 18, 0
        self.spine_room = 0
        self.spine_height = 130
        self.current = None
        self.more = self.saved = self.loading = self.preparing = False
        self.error = ''
        self.fit_idle = 0
        self.inspector_fit_idle = 0
        self.dimensions = None
        self.photo = Gtk.Image()
        self.inspection_photo = Gtk.Image()
        self.preview_size = 92
        self.connect('destroy',self.dispose)
        self.connect('unmap',lambda *_:self.close_inspector(restore_focus=False))
        self.stack = Gtk.Stack(hhomogeneous=False,vhomogeneous=False)
        self.pack_start(self.stack,True,True,0)
        self.scene = Gtk.Box(spacing=13)
        self.stack.add_named(self.scene,'shelf')
        self.inspector = RecordInspector(self.close_inspector,self.open_inspected_details)
        self.stack.add_named(self.inspector,'inspect')
        self.stack.connect('size-allocate',self.fit_inspector)
        cabinet = Gtk.Overlay()
        cabinet.get_style_context().add_class('record-cabinet')
        self.canvas = ShelfDrawing(self.paint_cabinet)
        self.canvas.set_size_request(260, 172)
        self.texture = None
        cabinet.add(self.canvas)
        self.scene.pack_start(cabinet,True,True,0)
        self.plaque = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                             halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
        self.plaque.get_style_context().add_class('record-plaque')
        self.plaque.pack_start(caption(text('My collection','Моя коллекция'),'record-plaque-title'),False,False,0)
        self.count = caption('','record-muted')
        self.plaque.pack_start(self.count,False,False,0)
        cabinet.add_overlay(self.plaque)
        self.rail = Gtk.Box(spacing=2, halign=Gtk.Align.FILL, valign=Gtk.Align.END)
        self.left, self.right = Gtk.Box(spacing=2), Gtk.Box(spacing=2)
        self.left.set_halign(Gtk.Align.END);self.right.set_halign(Gtk.Align.START)
        self.sleeve = Sleeve()
        self.sleeve_key = keyboard_click(key('',lambda:self.inspect_selected(),'record-inspect-sleeve'))
        self.sleeve_key.remove(self.sleeve_key.get_child())
        self.sleeve_key.add(self.sleeve)
        self.sleeve_key.get_accessible().set_name(text('Inspect album cover','Рассмотреть обложку'))
        self.sleeve_key.connect('state-flags-changed',self.sleeve.highlight)
        self.rail.pack_start(self.left,True,True,0)
        self.rail.pack_start(self.sleeve_key,False,False,0)
        self.rail.pack_start(self.right,True,True,0)
        cabinet.add_overlay(self.rail)

        self.detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self.detail.get_style_context().add_class('record-detail')
        self.detail.set_size_request(234,-1)
        panel = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                   vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,overlay_scrolling=False)
        panel.get_style_context().add_class('record-detail-scroll')
        panel.add(self.detail)
        self.scene.pack_end(panel,False,False,0)
        # Gtk's NEVER policy measures the child's full width. Wrapped labels
        # and a compact action bar keep the side panel inside small windows.
        self.preview = Gtk.Image(halign=Gtk.Align.CENTER)
        self.preview_key = keyboard_click(key('',self.inspect_selected,'record-inspect-cover'))
        preview_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5,halign=Gtk.Align.CENTER)
        preview_content.pack_start(self.preview,False,False,0)
        preview_content.pack_start(caption(text('Inspect jacket','Рассмотреть конверт')+'  ↻',
                                           'record-inspector-hint'),False,False,0)
        self.preview_key.remove(self.preview_key.get_child())
        self.preview_key.add(preview_content)
        self.preview_key.get_accessible().set_name(text('Inspect jacket','Рассмотреть конверт'))
        self.detail.pack_start(self.preview_key,False,False,0)
        self.title = caption('','record-detail-title',True)
        self.title.set_lines(2);self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.metadata = caption('','record-muted',True)
        self.detail.pack_start(self.title,False,False,0)
        self.detail.pack_start(self.metadata,False,False,0)
        self.play_key = key('▶ '+text('Play full album','Слушать целиком'),self.play_selected,'stage-accent')
        self.play_key.get_accessible().set_name(text('Play full album','Слушать альбом целиком'))
        self.details_key = key(text('Album details','Об альбоме')+'  ›',self.open_selected)
        self.actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.actions.pack_start(self.play_key,True,True,0)
        self.actions.pack_start(self.details_key,True,True,0)
        self.detail.pack_start(self.actions,False,False,0)
        self.detail.pack_start(Gtk.Separator(),False,False,3)
        self.detail.pack_start(caption(text('Physical editions','Физические издания'),'record-format-label'),False,False,0)
        self.format = Gtk.ComboBoxText()
        self.format.get_style_context().add_class('record-format')
        self.format.append('Vinyl',text('Vinyl','Винил'));self.format.append('CD','CD');self.format.set_active(0)
        self.detail.pack_start(self.format,False,False,0)
        markets = Gtk.Box(spacing=3)
        self.shops = {}
        for vendor in ('Discogs','eBay','Ozon'):
            shop = key(vendor+' ↗',lambda value=vendor:self.open_shop(value),'stage-tab')
            self.shops[vendor] = shop
            markets.pack_start(shop,True,True,0)
        self.detail.pack_start(markets,False,False,0)
        self.want = key('',self.toggle_wanted)
        self.detail.pack_start(self.want,False,False,0)
        self.message = caption('','record-muted',True)
        self.detail.pack_start(self.message,False,False,0)

        self.pager = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
        self.previous = keyboard_click(key('‹',lambda:self.turn(-1),'record-plaque-key'))
        self.following = keyboard_click(key('›',lambda:self.turn(1),'record-plaque-key'))
        self.previous.get_accessible().set_name(text('Previous shelf','Предыдущая полка'))
        self.following.get_accessible().set_name(text('Next shelf','Следующая полка'))
        self.filter_key = keyboard_click(key(text('Want to buy','Хочу купить'),self.toggle_filter,'record-plaque-key'))
        for control in (self.previous,self.filter_key,self.following):self.pager.pack_start(control,False,False,0)
        cabinet.add_overlay(self.pager)
        cabinet.connect('size-allocate',self.fit)
        cabinet.add_events(Gdk.EventMask.SCROLL_MASK)
        cabinet.connect('scroll-event',self.on_scroll)

        self.status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9,
                              halign=Gtk.Align.CENTER,valign=Gtk.Align.CENTER)
        self.status.get_style_context().add_class('record-shelf-status')
        self.status.get_style_context().add_class('record-detail')
        self.status_title = caption('','record-detail-title')
        self.status_detail = caption('','record-muted',True)
        self.status_detail.set_max_width_chars(42)
        self.status_spinner = Gtk.Spinner(halign=Gtk.Align.START)
        self.status_retry = key(text('Try again','Повторить'),retry)
        self.status_filter = key('',self.toggle_filter)
        controls = Gtk.Box(spacing=8)
        for control in (self.status_retry,self.status_filter):
            controls.pack_start(control,False,False,0)
        for child in (self.status_spinner,self.status_title,self.status_detail,controls):
            self.status.pack_start(child,False,False,0)
        self.pack_start(self.status,True,True,0)
        self.show_all()
        self.stack.hide()

    def paint_cabinet(self, cr):
        widget = self.canvas
        width,height = widget.get_allocated_width(),widget.get_allocated_height()
        y,scene_height = cabinet_geometry(width,height)
        c = widget.c
        c.cairo_save(cr)
        rounded(c,cr,0,y,width,scene_height,20);c.cairo_clip(cr)
        if self.texture is None:
            path = Path(__file__).resolve().parent/'assets'/'record-shelf.jpg'
            if not path.is_file():path = Path(__file__).resolve().parent.parent/'assets'/'record-shelf.jpg'
            try:self.texture = GdkPixbuf.Pixbuf.new_from_file(str(path))
            except GLib.Error:self.texture = False
        if self.texture:
            native_width = self.texture.get_width()
            scale = scene_height/self.texture.get_height()
            # Preserve the source's lamp, camera, plant and headphones. Only
            # the unoccupied walnut between them follows the cabinet's width.
            left_end, right_start = native_width*.405,native_width*.685
            left = round(left_end*scale)
            right = width-round((native_width-right_start)*scale)
            for start,end,source_start,source_end in (
                    (0,left,0,left_end),(left,right,left_end,right_start),(right,width,right_start,native_width)):
                if end <= start:continue
                stretch=(end-start)/(source_end-source_start)
                c.cairo_save(cr)
                c.cairo_rectangle(cr,start,y,end-start,scene_height);c.cairo_clip(cr)
                widget.paint_pixbuf(cr,self.texture,start-source_start*stretch,y,native_width*stretch,scene_height)
                c.cairo_restore(cr)
        else:
            c.cairo_set_source_rgba(cr,.19,.105,.059,1.);c.cairo_paint(cr)
            c.cairo_set_source_rgba(cr,.42,.24,.11,1.)
            for line in (.38,.94):c.cairo_rectangle(cr,0,y+scene_height*line,width,6)
            c.cairo_fill(cr)
        c.cairo_restore(cr)
        return False

    def fit(self, _cabinet, area):
        dimensions = area.width,area.height
        if dimensions != self.dimensions:
            self.dimensions = dimensions
            if not self.fit_idle:self.fit_idle = GLib.idle_add(self.apply_fit)

    def apply_fit(self):
        self.fit_idle = 0
        width,height = self.dimensions
        y,scene_height = cabinet_geometry(width,height)
        self.plaque.set_margin_top(max(5,int(y+scene_height*.18)))
        self.pager.set_margin_bottom(int(y+scene_height*.012))
        self.rail.set_margin_bottom(int(y+max(31,scene_height*.063)))
        inset = max(12,int(width*.075))
        far_inset = max(9,inset//2)
        self.rail.set_margin_start(inset);self.rail.set_margin_end(far_inset)
        size = max(76,min(int(scene_height*.48),int(width*.37),300))
        self.sleeve.set_size_request(size+16,size)
        dense = height < 340
        style = self.get_style_context()
        (style.add_class if dense else style.remove_class)('record-shelf-dense')
        self.detail.set_spacing(4 if dense else 7)
        self.actions.set_orientation(Gtk.Orientation.HORIZONTAL if dense else Gtk.Orientation.VERTICAL)
        self.play_key.set_label('▶ '+(text('Full album','Целиком') if dense else text('Play full album','Слушать целиком')))
        preview_size = max(48,min(152,int(height*(.21 if dense else .27))))
        if preview_size != self.preview_size:
            self.preview_size = preview_size
            self.update_preview(self.photo.get_pixbuf())
        room = width-size-16-inset-far_inset-4
        capacity = max(4,min(28,(room-48)//30))
        spine_height = max(62,int(size*.89))
        if (capacity,room,spine_height) != (self.capacity,self.spine_room,self.spine_height):
            index = self.page*self.capacity
            self.capacity = capacity
            self.spine_room = room
            self.spine_height = spine_height
            self.page = index//capacity
            self.render_rail()
        return False

    def fit_inspector(self, _stack, area):
        compact = area.height < 330
        if not self.inspector_fit_idle and self.inspector.compact != compact:
            self.inspector_fit_idle = GLib.idle_add(self.apply_inspector_fit)

    def apply_inspector_fit(self):
        self.inspector_fit_idle = 0
        self.inspector.set_compact(self.stack.get_allocated_height() < 330)
        return False

    def dispose(self, _shelf):
        if self.fit_idle:GLib.source_remove(self.fit_idle);self.fit_idle=0
        if self.inspector_fit_idle:GLib.source_remove(self.inspector_fit_idle);self.inspector_fit_idle=0
        self.photo.destroy()
        self.inspection_photo.destroy()

    def feed(self, source, values, more, loading=False, error=''):
        if self.source != source:
            self.close_inspector(restore_focus=False)
            self.source, self.saved, self.current, self.page = source, False, None, 0
        albums = {}
        for value in values:
            if ref := release_reference(source,value):albums.setdefault(ref['uri'],ref)
        self.albums, self.more, self.loading, self.error = list(albums.values()), more, loading, error
        self.refresh()

    def refresh(self):
        self.items = ([v for v in self.wishlist.items.values() if v['source']==self.source]
                      if self.saved else self.albums)
        self.stack.set_visible(bool(self.items))
        self.status.set_visible(not self.items)
        self.update_status()
        current = next((v for v in self.items if self.current and v['uri']==self.current['uri']),None)
        self.page = min(self.page,max(0,(len(self.items)-1)//self.capacity))
        self.render_rail()
        self.select(current or next(iter(self.items[self.page*self.capacity:]),None))

    def update_status(self):
        wait = self.loading and not self.saved and not self.items
        failed = bool(self.error and not self.saved and not self.items)
        if wait:
            title = text('Loading albums…','Загружаю альбомы…')
            detail = ''
        elif failed:
            title = text('Could not load albums','Не удалось загрузить альбомы')
            detail = self.error
        elif self.saved:
            title = text('Your wishlist is empty','В списке «Хочу купить» пока пусто')
            detail = text('Save a release to find it here later.','Сохрани релиз, чтобы позже вернуться к поиску издания.')
        else:
            title = text('No saved albums yet','Пока нет сохранённых альбомов')
            detail = text('Albums saved in this music service will appear here.',
                          'Здесь появятся альбомы, сохранённые в выбранном сервисе.')
        self.status_title.set_text(title)
        self.status_detail.set_text(detail)
        self.status_detail.set_visible(bool(detail))
        self.status_spinner.set_visible(wait)
        (self.status_spinner.start if wait else self.status_spinner.stop)()
        self.status_retry.set_visible(failed)
        self.status_filter.set_label(text('All albums','Все альбомы') if self.saved else text('Want to buy','Хочу купить'))
        self.status_filter.set_visible(self.saved or any(v['source']==self.source for v in self.wishlist.items.values()))

    def render_rail(self):
        for box in (self.left,self.right):
            for child in box.get_children():child.destroy()
        self.spines = []
        start = self.page*self.capacity
        values = self.items[start:start+self.capacity]
        halves = (len(values)+1)//2
        widths = self.jacket_widths(len(values),halves)
        for index, value in enumerate(values):
            side = -1 if index < halves else 1
            width = widths[index]
            spine = keyboard_click(RecordSpine(value,width,self.spine_height,side,width>=41,self.artwork,self.select))
            spine.set_selected(bool(self.current and self.current['uri']==value['uri']))
            box = self.left if side < 0 else self.right
            box.pack_start(spine,False,False,0)
            self.spines.append((spine,value))
        self.left.show_all();self.right.show_all()
        self.count.set_text(text(f'{len(self.items)} releases',f'Релизов на полке: {len(self.items)}'))
        self.filter_key.set_label((text('All albums','Все альбомы') if self.saved else
                                   text('Want to buy','Хочу купить')))
        self.previous.set_sensitive(self.page>0)
        self.following.set_sensitive(start+self.capacity<len(self.items) or (self.more and not self.saved and not self.loading))

    def jacket_widths(self, count, split):
        """Use spare shelf space to turn the nearest jackets toward the viewer."""
        room = max(0,self.spine_room-2*count)
        widths = [max(18,min(28,room//max(1,count)+(i%3)-1)) for i in range(count)]
        spare = max(0,room-sum(widths))
        front_positions = [i for distance in range(3)
                           for i in (split-1-distance,split+distance) if 0 <= i < count]
        opened = front_positions[:spare//17]
        for position,i in enumerate(opened):
            gain = min(spare//(len(opened)-position),68-widths[i])
            widths[i] += gain
            spare -= gain
        return widths

    def turn(self, direction):
        page = self.page+direction
        if 0 <= page and page*self.capacity < len(self.items):
            self.page = page;self.render_rail();self.select(self.items[page*self.capacity],animate=True)
        elif direction>0 and self.more and not self.saved and not self.loading:
            self.load_more()

    def on_scroll(self, _widget, event):
        if event.direction in (Gdk.ScrollDirection.RIGHT,Gdk.ScrollDirection.DOWN) and self.following.get_sensitive():
            self.turn(1);return True
        if event.direction in (Gdk.ScrollDirection.LEFT,Gdk.ScrollDirection.UP) and self.previous.get_sensitive():
            self.turn(-1);return True
        return False

    def select(self, value, animate=False):
        old_key = (self.current or {}).get('uri')
        self.current = value
        release = value or {}
        if old_key != release.get('uri'):
            self.close_inspector(restore_focus=False)
        if old_key != release.get('uri') or animate:
            self.message.set_text('')
            self.preparing = False
        for spine,item in self.spines:
            spine.set_selected(bool(value and item['uri']==value['uri']))
        self.title.set_text(release.get('title') or (text('Loading albums…','Загружаю альбомы…') if self.loading
            else text('The shelf is empty','Полка пока пуста')))
        year = str(release.get('releaseDate') or release.get('year') or '')[:4]
        self.metadata.set_text(' · '.join(str(v) for v in (release.get('artist'),year) if v))
        if old_key != release.get('uri') or animate:
            if value:
                self.artwork.load(self.photo,release.get('image',''),560,0,high_quality=True,
                                  keep_aspect=True,on_loaded=self.set_cover)
                self.set_cover(self.photo.get_pixbuf())
                if animate:self.sleeve.pull()
            else:
                self.photo._art_token = None
                self.photo.clear()
                self.set_cover(None)
        self.update_controls()

    def set_cover(self, pixels):
        self.sleeve.art = pixels
        self.sleeve.queue_draw()
        self.update_preview(pixels)

    def update_preview(self, pixels):
        if pixels:
            ratio = self.preview_size/max(pixels.get_width(),pixels.get_height())
            self.preview.set_from_pixbuf(pixels.scale_simple(max(1,round(pixels.get_width()*ratio)),
                max(1,round(pixels.get_height()*ratio)),GdkPixbuf.InterpType.BILINEAR))
        else:
            self.preview.clear()

    @property
    def inspector_open(self):
        return self.stack.get_visible_child() is self.inspector

    def inspect_selected(self):
        if not self.current or self.inspector_open:
            return
        self.inspect_origin = self.get_toplevel().get_focus()
        self.inspector.set_compact(self.stack.get_allocated_height() < 330)
        self.inspector.open(self.current,self.photo.get_pixbuf())
        self.stack.set_visible_child(self.inspector)
        self.inspector.canvas.grab_focus()
        if url := self.current.get('image'):
            def loaded(pixels):
                if self.inspector_open:
                    self.inspector.canvas.offer_art(pixels)
            self.artwork.load(self.inspection_photo,url,INSPECT_ART_SIZE,0,high_quality=True,
                              keep_aspect=True,on_loaded=loaded)

    def close_inspector(self, restore_focus=True):
        if not self.inspector_open:
            return
        self.inspection_photo._art_token = None
        self.inspection_photo.clear()
        self.stack.set_visible_child(self.scene)
        self.inspector.canvas.clear_faces()
        if restore_focus:
            origin = self.inspect_origin
            (origin if origin and origin.get_mapped() and origin.get_can_focus()
             else self.preview_key).grab_focus()
        self.inspect_origin = None

    def open_inspected_details(self):
        self.close_inspector(restore_focus=False)
        self.open_selected()

    def update_controls(self):
        self.play_key.set_sensitive(bool(self.current) and not (self.preparing or self.loading))
        for control in (self.preview_key,self.details_key,self.format,self.want,*self.shops.values()):
            control.set_sensitive(bool(self.current))
        marked = self.current and self.current['uri'] in self.wishlist.items
        self.want.set_label(('✓ ' if marked else '＋ ')+text('Want to buy','Хочу купить'))

    def toggle_filter(self):
        self.saved = not self.saved
        self.page = 0;self.refresh()

    def toggle_wanted(self):
        if not self.current:return
        try:self.wishlist.toggle(self.source,self.current)
        except OSError:
            self.message.set_text(text('Could not save the wishlist.','Не удалось сохранить список покупок.'))
            return
        self.refresh()

    def open_selected(self):
        if self.current:self.details(self.current)

    def play_selected(self):
        if self.current:
            self.preparing = True;self.update_controls()
            self.message.set_text(text('Loading the full track list…','Загружаю альбом целиком…'))
            self.play(self.current)

    def open_shop(self, vendor):
        if not self.current:return
        uri = edition_links(self.current,self.format.get_active_id()).get(vendor)
        if uri:
            try:Gtk.show_uri_on_window(self.get_toplevel(),uri,Gdk.CURRENT_TIME)
            except GLib.Error:self.message.set_text(text('Could not open the store.','Не удалось открыть магазин.'))
