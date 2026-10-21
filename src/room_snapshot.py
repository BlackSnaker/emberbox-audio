"""Render our own already-measured GTK tree once, without a desktop readback.

GTK 3 and Cairo are existing runtime libraries. Calling their C entry points
avoids adding a PyCairo binding solely to pass an opaque drawing context.
"""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache


@lru_cache(maxsize=1)
def bindings():
    cairo=C.CDLL(find_library('cairo'));gtk=C.CDLL(find_library('gtk-3'))
    for name,(result,*args) in {
        'cairo_image_surface_create':(C.c_void_p,C.c_int,C.c_int,C.c_int),
        'cairo_create':(C.c_void_p,C.c_void_p),
        'cairo_translate':(None,C.c_void_p,C.c_double,C.c_double),
        'cairo_surface_flush':(None,C.c_void_p),
        'cairo_image_surface_get_data':(C.c_void_p,C.c_void_p),
        'cairo_image_surface_get_stride':(C.c_int,C.c_void_p),
        'cairo_destroy':(None,C.c_void_p),'cairo_surface_destroy':(None,C.c_void_p),
    }.items():
        fn=getattr(cairo,name);fn.restype=result;fn.argtypes=args
    gtk.gtk_widget_draw.restype=None
    gtk.gtk_widget_draw.argtypes=[C.c_void_p,C.c_void_p]
    pointer=C.pythonapi.PyCapsule_GetPointer
    pointer.restype=C.c_void_p;pointer.argtypes=[C.py_object,C.c_char_p]
    return cairo,gtk,pointer


def snapshot(widget,allocation):
    """Return a single BGRA premultiplied frame; never save account UI to disk."""
    cairo,gtk,pointer=bindings()
    surface=cairo.cairo_image_surface_create(0,allocation.width,allocation.height)
    context=cairo.cairo_create(surface)
    mapped=widget.get_mapped()
    try:
        widget.show()
        if not mapped:widget.map()
        widget.get_preferred_size()
        widget.size_allocate(allocation)
        area=widget.get_allocation()
        cairo.cairo_translate(context,area.x,area.y)
        gtk.gtk_widget_draw(pointer(widget.__gpointer__,None),context)
        cairo.cairo_surface_flush(surface)
        stride=cairo.cairo_image_surface_get_stride(surface)
        data=C.string_at(cairo.cairo_image_surface_get_data(surface),stride*allocation.height)
        if stride!=allocation.width*4:
            data=b''.join(data[y*stride:y*stride+allocation.width*4] for y in range(allocation.height))
        return allocation.width,allocation.height,data
    finally:
        if not mapped:widget.unmap()
        cairo.cairo_destroy(context);cairo.cairo_surface_destroy(surface)


def warm_window(widget,window,allocation):
    """Prime GDK's GL-to-window compositor too, while our window is hidden."""
    native=window.get_window()
    if native is None:return
    cairo,gtk,pointer=bindings()
    gdk=C.CDLL(find_library('gdk-3'))
    class Rectangle(C.Structure):
        _fields_=[('x',C.c_int),('y',C.c_int),('width',C.c_int),('height',C.c_int)]
    cairo.cairo_region_create_rectangle.restype=C.c_void_p
    cairo.cairo_region_create_rectangle.argtypes=[C.POINTER(Rectangle)]
    cairo.cairo_region_destroy.restype=None;cairo.cairo_region_destroy.argtypes=[C.c_void_p]
    gdk.gdk_window_begin_draw_frame.restype=C.c_void_p
    gdk.gdk_window_begin_draw_frame.argtypes=[C.c_void_p,C.c_void_p]
    gdk.gdk_drawing_context_get_cairo_context.restype=C.c_void_p
    gdk.gdk_drawing_context_get_cairo_context.argtypes=[C.c_void_p]
    gdk.gdk_window_end_draw_frame.restype=None
    gdk.gdk_window_end_draw_frame.argtypes=[C.c_void_p,C.c_void_p]
    region=cairo.cairo_region_create_rectangle(C.byref(Rectangle(0,0,allocation.width,allocation.height)))
    mapped=widget.get_mapped();visible=widget.get_visible()
    context=None;handle=pointer(native.__gpointer__,None)
    try:
        widget.show()
        if not mapped:widget.map()
        widget.size_allocate(allocation)
        context=gdk.gdk_window_begin_draw_frame(handle,region)
        if context:
            cr=gdk.gdk_drawing_context_get_cairo_context(context)
            if cr:gtk.gtk_widget_draw(pointer(widget.__gpointer__,None),cr)
    finally:
        if context:gdk.gdk_window_end_draw_frame(handle,context)
        if not mapped:widget.unmap()
        if not visible:widget.hide()
        cairo.cairo_region_destroy(region)
