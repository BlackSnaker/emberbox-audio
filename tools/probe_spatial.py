#!/usr/bin/env python3
"""Developer prototype: clear E-AC-3 JOC chunks -> native binaural PCM in memory.

Requires an explicitly supplied OpenJOC 1.7 ABI library and a short local raw
fixture. No network, account access, sound-device output or playback integration.
It does not enable Apple Music Atmos. See docs/ATMOS_PROTOTYPE.md.
"""
import argparse
import array
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import time


class Config(C.Structure):
    _fields_ = [('struct_size', C.c_uint32), ('render_mode', C.c_uint32),
        ('speaker_layout', C.c_char_p), ('downmix', C.c_uint32), ('drc', C.c_uint32),
        ('drc_boost_percent', C.c_uint8), ('drc_cut_percent', C.c_uint8),
        ('validation_profile', C.c_uint32), ('sofa_data', C.c_void_p), ('sofa_size', C.c_size_t),
        ('virtual_layout', C.c_char_p), ('lfe_policy', C.c_uint32), ('dialnorm_mode', C.c_uint32),
        ('custom_speaker_layout', C.c_void_p), ('hrtf_preset', C.c_uint32),
        ('reserved_v1_6_padding', C.c_uint32), ('listener_orientation_pull_samples', C.c_uint32)]


class Frame(C.Structure):
    _fields_ = [('struct_size', C.c_uint32), ('sample_format', C.c_uint32),
        ('sample_rate', C.c_uint32), ('channel_count', C.c_uint32),
        ('sample_count', C.c_size_t), ('pts_samples', C.c_int64),
        ('data', C.c_void_p), ('data_len', C.c_size_t), ('layout_name', C.c_char_p),
        ('channel_labels', C.c_void_p), ('channel_label_count', C.c_size_t)]


def probe(library, source, chunk_size=4096):
    """Exercise the framework-neutral streaming C ABI, including its drain tail."""
    if not source.is_file() or not 0 < source.stat().st_size <= 16 * 1024 * 1024:
        raise ValueError('Supply a nonempty raw fixture of at most 16 MiB')
    if not 1 <= chunk_size <= 65536:
        raise ValueError('Chunk size must be between 1 and 65536')
    lib = C.CDLL(str(library.resolve()))

    def bind(name, result, *arguments):
        fn = getattr(lib, 'openjoc_' + name)
        fn.restype, fn.argtypes = result, arguments
        return fn

    abi = bind('get_abi_version', C.c_uint32)()
    if abi >> 16 != 1 or abi & 65535 < 7:
        raise ValueError('OpenJOC ABI 1.7 or a compatible newer 1.x is required')
    init = bind('decoder_config_init_v1_7', C.c_int, C.POINTER(Config))
    create = bind('stream_decoder_create', C.c_int, C.POINTER(Config), C.POINTER(C.c_void_p))
    destroy = bind('stream_decoder_destroy', None, C.c_void_p)
    send = bind('stream_decoder_send_chunk', C.c_int, C.c_void_p, C.c_void_p,
                C.c_size_t, C.c_int64, C.c_uint32)
    receive = bind('stream_decoder_receive_frame', C.c_int, C.c_void_p, C.POINTER(Frame))
    drain = bind('stream_decoder_drain', C.c_int, C.c_void_p)
    staged = bind('stream_decoder_get_staged_bytes', C.c_size_t, C.c_void_p)
    frame_init = bind('pcm_frame_init', C.c_int, C.POINTER(Frame))
    inspect = bind('stream_decoder_copy_live_inspection_json', C.c_int, C.c_void_p,
                   C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t))

    def check(status, allowed=(0, 1, 2)):
        if status not in allowed:
            raise RuntimeError(f'OpenJOC status {status}; no verified spatial output')

    config, handle = Config(), C.c_void_p()
    check(init(C.byref(config)))
    config.render_mode, config.virtual_layout = 2, b'7.1.4'
    check(create(C.byref(config), C.byref(handle)))
    start = time.perf_counter()
    digest = hashlib.sha256()
    frames = calls = max_staged = 0
    rate = 0
    peak = 0.0

    def consume():
        nonlocal frames, calls, rate, peak
        # All native work is confined to this explicitly invoked developer
        # process, never a GTK callback or the MusicKit playback thread.
        while True:
            if time.perf_counter() - start > 30:
                raise TimeoutError('Spatial prototype exceeded its 30-second budget')
            frame = Frame()
            check(frame_init(C.byref(frame)))
            status = receive(handle, C.byref(frame))
            if status in (0, 1, 3):
                return status
            check(status, (2,))
            if (frame.sample_format != 1 or frame.channel_count != 2 or
                    not 8000 <= frame.sample_rate <= 192000 or
                    not 0 < frame.data_len <= 1024 * 1024 or not frame.data or
                    frame.data_len != frame.sample_count * 2 * 4):
                raise RuntimeError('Unexpected binaural PCM format')
            if rate and rate != frame.sample_rate:
                raise RuntimeError('Unexpected sample-rate change')
            rate = frame.sample_rate
            frames += frame.sample_count
            calls += 1
            if frames > rate * 30:
                raise ValueError('Use a fixture of at most 30 seconds')
            # Native frame storage expires on the next decoder call.
            pcm = C.string_at(frame.data, frame.data_len)
            samples = array.array('f')
            samples.frombytes(pcm)
            if not all(map(math.isfinite, samples)):
                raise RuntimeError('Non-finite output')
            peak = max(peak, max(map(abs, samples), default=0))
            digest.update(pcm)

    try:
        with source.open('rb') as stream:
            while data := stream.read(chunk_size):
                chunk = C.create_string_buffer(data)
                status = send(handle, chunk, len(data), -(1 << 63), 0)
                if status == 4:  # Input not consumed: empty the output, then retry.
                    consume()
                    status = send(handle, chunk, len(data), -(1 << 63), 0)
                check(status)
                max_staged = max(max_staged, staged(handle))
                consume()
        check(drain(handle), (0, 1, 2, 3, 4))
        consume()
        output = C.create_string_buffer(65536)
        required = C.c_size_t()
        check(inspect(handle, output, len(output), C.byref(required)), (0,))
        observation = json.loads(output.value)
        # Inspect the stream itself; an extension, catalogue label, six-channel
        # carrier or filename is insufficient evidence for this result.
        confirmed = observation.get('joc_present') is True
        if not confirmed or not frames:
            raise RuntimeError('The decoder did not confirm rendered JOC audio')
        elapsed = time.perf_counter() - start
        return {'schema': 1, 'decoderAbi': f'{abi >> 16}.{abi & 65535}',
            'jocConfirmed': True, 'renderer': 'OpenJOC binaural / SADIE II D1 / 7.1.4',
            'sampleRate': rate, 'channels': 2, 'frames': frames, 'blocks': calls,
            'audioSeconds': round(frames / rate, 6), 'wallSeconds': round(elapsed, 6),
            'wallToAudioRatio': round(elapsed / (frames / rate), 4),
            'peak': peak, 'allFinite': True, 'pcmSha256': digest.hexdigest(),
            'maximumStagedBytes': max_staged, 'appleMusicPlaybackVerified': False}
    finally:
        destroy(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True, help='Trusted libopenjoc_capi.so')
    parser.add_argument('--input', type=Path, required=True, help='Short, clear local .ec3 test fixture')
    parser.add_argument('--chunk-size', type=int, default=4096)
    args = parser.parse_args()
    try:
        result = probe(args.library, args.input, args.chunk_size)
    except (OSError, ValueError, RuntimeError, TimeoutError, AttributeError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
