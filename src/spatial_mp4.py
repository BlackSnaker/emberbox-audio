"""Bounded MP4 box traversal; payload bytes are never interpreted as boxes."""


def boxes(data,start,end):
    while start<end:
        if end-start<8:raise ValueError('Truncated MP4 box')
        size=int.from_bytes(data[start:start+4],'big');kind=bytes(data[start+4:start+8]);header=8
        if size==1:
            if end-start<16:raise ValueError('Truncated MP4 box')
            size=int.from_bytes(data[start+8:start+16],'big');header=16
        elif size==0:size=end-start
        if size<header or size>end-start:raise ValueError('Invalid MP4 box size')
        yield kind,start,start+header,start+size
        start+=size
