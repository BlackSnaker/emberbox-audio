#!/usr/bin/env python3
"""Firefox native-messaging framing; carries only typed music operations."""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading

MAX_MESSAGE = 2_000_000


def read_message(stream):
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError('Short native-messaging header')
    size = struct.unpack('@I', header)[0]
    if not 0 < size <= MAX_MESSAGE:
        raise ValueError('Invalid native-messaging size')
    data = stream.read(size)
    if len(data) != size:
        raise ValueError('Short native-messaging body')
    return json.loads(data)


def write_message(stream, value):
    raw = json.dumps(value, separators=(',', ':')).encode()
    if len(raw) > MAX_MESSAGE:
        raise ValueError('Native message too large')
    stream.write(struct.pack('@I', len(raw)) + raw)
    stream.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', default='emberbox-audio')
    args, _ = parser.parse_known_args()
    if args.app not in ('emberbox-audio', 'gruvbox-spotify-widget'):
        return 1
    path = Path(os.environ.get('XDG_RUNTIME_DIR', Path.home()/'.cache'))/args.app/'apple-music.sock'
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.connect(str(path))
    except OSError:
        return 1

    def incoming():
        try:
            while True:
                value = read_message(sys.stdin.buffer)
                if value is None:
                    break
                raw = json.dumps(value).encode()
                if len(raw) > MAX_MESSAGE:
                    break
                connection.sendall(raw+b'\n')
        except (OSError, ValueError):
            pass
        finally:
            connection.shutdown(socket.SHUT_RDWR)
    threading.Thread(target=incoming,daemon=True).start()
    try:
        with connection.makefile('rb') as stream:
            for line in iter(lambda:stream.readline(MAX_MESSAGE+1),b''):
                if len(line)>MAX_MESSAGE:
                    break
                write_message(sys.stdout.buffer,json.loads(line))
    except (OSError,ValueError):
        pass
    finally:
        connection.close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
