"""Embedded warm-metal service emblems; no icon-pack or network dependency."""
from gi.repository import Gtk, GdkPixbuf

MARKS = {
    'spotify': '<circle cx="16" cy="16" r="10" fill="#d4b888" stroke="none"/><path d="M9 13 Q16 10 23 14 M10 17 Q16 14 22 18 M11 21 Q16 18 21 21" stroke="#302b28" stroke-width="1.8"/>',
    'apple-music': '<path d="M14 21 V9 L24 7 V19 M14 12 L24 10"/><ellipse cx="10.5" cy="22" rx="3.5" ry="2.8" fill="#d4b888" stroke="none"/><ellipse cx="20.5" cy="20" rx="3.5" ry="2.8" fill="#d4b888" stroke="none"/>',
    'youtube': '<rect x="5" y="9" width="22" height="15" rx="5"/><path d="M14 13 L21 16.5 L14 20 Z" fill="#d4b888" stroke="none"/>',
    'yandex-music': '<path d="M17 5 L19 12 L26 9 L22 16 L28 19 L20 20 L20 27 L15 22 L10 27 L11 19 L4 17 L12 14 L9 7 L15 11 Z" fill="#d4b888" stroke="none"/>',
}


def service_icon(source, size=32):
    mark = MARKS.get(source, MARKS['apple-music'])
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
           '<defs><linearGradient id="m" x2=".8" y2="1"><stop stop-color="#43403b"/><stop offset="1" stop-color="#222625"/></linearGradient></defs>'
           '<rect x=".8" y=".8" width="30.4" height="30.4" rx="10" fill="url(#m)" stroke="#aa9470" stroke-opacity=".3"/>'
           '<path d="M8 2.5 H24" stroke="#f4dbab" stroke-opacity=".15"/>'
           '<g fill="none" stroke="#d4b888" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+mark+'</g></svg>')
    loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
    loader.set_size(size,size); loader.write(svg.encode()); loader.close()
    image = Gtk.Image.new_from_pixbuf(loader.get_pixbuf())
    image.set_can_focus(False)
    return image
