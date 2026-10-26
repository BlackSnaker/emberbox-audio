#!/usr/bin/env python3
"""Build the exact VU sprites offline; never rasterise SVG on animation ticks."""
import math
import hashlib
import json
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


REFERENCE=Path(__file__).resolve().parents[1]/'tests/fixtures/tube-meter-v1.json'


def reference(atlas):
    frames=[]
    for index in range(201):
        image=atlas.new_subpixbuf(index%FRAME_COLUMNS*FRAME_WIDTH,
            index//FRAME_COLUMNS*FRAME_HEIGHT,FRAME_WIDTH,FRAME_HEIGHT)
        raw=image.get_pixels();stride=image.get_rowstride()
        rgba=b''.join(raw[y*stride:y*stride+FRAME_WIDTH*4] for y in range(FRAME_HEIGHT))
        frames.append({'svg_sha256':hashlib.sha256(tube_svg(index).encode('utf-8')).hexdigest(),
                       'rgba_sha256':hashlib.sha256(rgba).hexdigest()})
    return {'schema':1,'width':FRAME_WIDTH,'height':FRAME_HEIGHT,'columns':FRAME_COLUMNS,
            'atlas_sha256':hashlib.sha256(ATLAS.read_bytes()).hexdigest(),'frames':frames}


def render():
    atlas=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,True,8,
        FRAME_COLUMNS*FRAME_WIDTH,math.ceil(201/FRAME_COLUMNS)*FRAME_HEIGHT)
    atlas.fill(0)
    for index in range(201):
        image=pixbuf(tube_svg(index),FRAME_WIDTH,FRAME_HEIGHT)
        image.copy_area(0,0,FRAME_WIDTH,FRAME_HEIGHT,atlas,
            index%FRAME_COLUMNS*FRAME_WIDTH,index//FRAME_COLUMNS*FRAME_HEIGHT)
    atlas.savev(str(ATLAS),'png',[],[])
    # Commit the reviewed source/pixel reference with an intentional artwork
    # update. CI verifies these exact assets without platform SVG/font rendering.
    REFERENCE.parent.mkdir(parents=True,exist_ok=True)
    REFERENCE.write_text(json.dumps(reference(atlas),indent=2)+'\n')
    print(ATLAS)
    print(REFERENCE)


if __name__=='__main__':render()
