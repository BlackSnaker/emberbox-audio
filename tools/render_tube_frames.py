#!/usr/bin/env python3
"""Build the exact VU sprites offline; never rasterise SVG on animation ticks."""
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
gi.require_version('Atk','1.0')
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf
from hardware_controls import pixbuf
from tube_meter import ATLAS,FRAME_COLUMNS,FRAME_WIDTH,FRAME_HEIGHT,tube_svg


def render():
    atlas=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,True,8,
        FRAME_COLUMNS*FRAME_WIDTH,math.ceil(201/FRAME_COLUMNS)*FRAME_HEIGHT)
    atlas.fill(0)
    for index in range(201):
        image=pixbuf(tube_svg(index),FRAME_WIDTH,FRAME_HEIGHT)
        image.copy_area(0,0,FRAME_WIDTH,FRAME_HEIGHT,atlas,
            index%FRAME_COLUMNS*FRAME_WIDTH,index//FRAME_COLUMNS*FRAME_HEIGHT)
    atlas.savev(str(ATLAS),'png',[],[])
    print(ATLAS)


if __name__=='__main__':render()
