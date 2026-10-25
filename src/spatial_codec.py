"""Native licensed decryption and JOC rendering. Imported by the audio worker only."""
import array
import ctypes as C
import json
import math
import time


def key_identifier(data):
    """Read public Widevine PSSH metadata, including trailing protobuf fields."""
    if len(data)>131072 or len(data)<32 or data[4:8]!=b'pssh' or int.from_bytes(data[:4],'big')!=len(data):
        raise ValueError('Invalid spatial init data')
    if data[12:28]!=bytes.fromhex('edef8ba979d64acea3c827dcd51d21ed'):raise ValueError('Unsupported DRM system')
    if data[8] not in (0,1):raise ValueError('Unsupported PSSH version')
    offset=28
    if data[8]==1:
        count=int.from_bytes(data[offset:offset+4],'big')
        if count>32:raise ValueError('Too many PSSH identifiers')
        offset+=4+count*16
    size=int.from_bytes(data[offset:offset+4],'big');payload=data[offset+4:offset+4+size]
    if len(payload)!=size or offset+4+size!=len(data):raise ValueError('Truncated PSSH')
    pos=0
    def varint():
        nonlocal pos
        value=0
        for shift in range(0,70,7):
            if pos>=len(payload):raise ValueError('Truncated PSSH field')
            byte=payload[pos];pos+=1;value|=(byte&127)<<shift
            if not byte&128:return value
        raise ValueError('Invalid PSSH field')
    while pos<len(payload):
        tag=varint();field,wire=tag>>3,tag&7
        if wire==0:varint()
        elif wire==2:
            length=varint()
            if length>len(payload)-pos:raise ValueError('Truncated PSSH field')
            value=payload[pos:pos+length];pos+=length
            if field==2 and length==16:return value
        elif wire in (1,5):pos+=8 if wire==1 else 4
        else:raise ValueError('Unsupported PSSH field')
    raise ValueError('Missing declared key identifier')


def bind(lib,name,result,*arguments):
    fn=getattr(lib,name);fn.restype=result;fn.argtypes=list(arguments);return fn


class Cdm:
    def __init__(self,library,module):
        self.lib=C.CDLL(library);self.handle=None
        self.create=bind(self.lib,'ember_cdm_create',C.c_void_p,C.c_char_p)
        self.state=bind(self.lib,'ember_cdm_state',C.c_int,C.c_void_p)
        self.destroy=bind(self.lib,'ember_cdm_destroy',None,C.c_void_p)
        for name in ('certificate','generate','update'):
            setattr(self,name+'_fn',bind(self.lib,'ember_cdm_'+name,C.c_int,C.c_void_p,C.c_void_p,C.c_uint32))
        self.message=bind(self.lib,'ember_cdm_message',C.c_int,C.c_void_p,C.c_void_p,C.c_uint32)
        self.usable=bind(self.lib,'ember_cdm_usable',C.c_int,C.c_void_p)
        self.exception=bind(self.lib,'ember_cdm_exception',C.c_int,C.c_void_p)
        self.callback_type=C.CFUNCTYPE(None,C.c_void_p,C.c_uint32)
        self.packet=bind(self.lib,'ember_cdm_packet',C.c_int,C.c_void_p,C.c_void_p,C.c_uint32,C.c_void_p,C.c_void_p,C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint32,self.callback_type)
        self.handle=self.create(module.encode())
        if not self.handle:raise RuntimeError('SPATIAL_CDM_UNAVAILABLE')
        until=time.monotonic()+3
        while self.state(self.handle)==0 and time.monotonic()<until:time.sleep(.01)
        if self.state(self.handle)!=1:self.close();raise RuntimeError('SPATIAL_CDM_UNAVAILABLE')

    def call(self,method,data):
        if not 0<len(data)<=131072:raise ValueError('Invalid CDM message size')
        if getattr(self,method+'_fn')(self.handle,data,len(data))<0:
            error=RuntimeError('SPATIAL_LICENSE_REJECTED');error.diagnostics={'stage':method,'exception':self.exception(self.handle)};raise error

    def challenge(self,init):
        self.call('generate',init);out=C.create_string_buffer(131072);until=time.monotonic()+5
        while time.monotonic()<until:
            count=self.message(self.handle,out,len(out))
            if count:return out.raw[:count]
            time.sleep(.01)
        raise RuntimeError('SPATIAL_LICENSE_TIMEOUT')

    def decode_sample(self,data,crypto,kid,deliver):
        errors=[]
        @self.callback_type
        def output(pointer,size):
            try:deliver(pointer,size)
            except Exception as error:errors.append(error)
        pairs=(C.c_uint32*(len(crypto['pairs'])*2))(*(v for pair in crypto['pairs'] for v in pair))
        selected=kid if crypto['kid']==b'\0'*16 else crypto['kid']
        status=self.packet(self.handle,data,len(data),selected,crypto['iv'],pairs,len(crypto['pairs']),crypto['scheme'],crypto['crypt'],crypto['skip'],output)
        if errors:raise errors[0]
        if status!=1:raise RuntimeError('SPATIAL_NO_KEY' if status==-102 else 'SPATIAL_DECRYPT_FAILED')

    def close(self):
        if self.handle:self.destroy(self.handle);self.handle=None


class Config(C.Structure):
    _fields_=[('struct_size',C.c_uint32),('render_mode',C.c_uint32),('speaker_layout',C.c_char_p),
        ('downmix',C.c_uint32),('drc',C.c_uint32),('boost',C.c_uint8),('cut',C.c_uint8),
        ('validation',C.c_uint32),('sofa',C.c_void_p),('sofa_size',C.c_size_t),
        ('virtual_layout',C.c_char_p),('lfe',C.c_uint32),('dialnorm',C.c_uint32),
        ('custom',C.c_void_p),('hrtf',C.c_uint32),('reserved',C.c_uint32),('orientation',C.c_uint32)]


class Frame(C.Structure):
    _fields_=[('size',C.c_uint32),('format',C.c_uint32),('rate',C.c_uint32),('channels',C.c_uint32),
        ('samples',C.c_size_t),('pts',C.c_int64),('data',C.c_void_p),('length',C.c_size_t),
        ('layout',C.c_char_p),('labels',C.c_void_p),('label_count',C.c_size_t)]


class Joc:
    def __init__(self,library,output):
        lib=C.CDLL(library);self.lib=lib;self.output=output;self.confirmed=False;self.handle=C.c_void_p()
        abi=bind(lib,'openjoc_get_abi_version',C.c_uint32)()
        if abi>>16!=1 or abi&65535<7:raise RuntimeError('SPATIAL_DECODER_VERSION')
        init=bind(lib,'openjoc_decoder_config_init_v1_7',C.c_int,C.POINTER(Config))
        create=bind(lib,'openjoc_stream_decoder_create',C.c_int,C.POINTER(Config),C.POINTER(C.c_void_p))
        self.destroy=bind(lib,'openjoc_stream_decoder_destroy',None,C.c_void_p)
        self.send=bind(lib,'openjoc_stream_decoder_send_chunk',C.c_int,C.c_void_p,C.c_void_p,C.c_size_t,C.c_int64,C.c_uint32)
        self.receive=bind(lib,'openjoc_stream_decoder_receive_frame',C.c_int,C.c_void_p,C.POINTER(Frame))
        self.init_frame=bind(lib,'openjoc_pcm_frame_init',C.c_int,C.POINTER(Frame))
        self.drain=bind(lib,'openjoc_stream_decoder_drain',C.c_int,C.c_void_p)
        self.inspect=bind(lib,'openjoc_stream_decoder_copy_live_inspection_json',C.c_int,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t))
        config=Config()
        if init(C.byref(config))!=0:raise RuntimeError('SPATIAL_DECODER_INIT')
        config.render_mode=2;config.virtual_layout=b'7.1.4'
        if create(C.byref(config),C.byref(self.handle))!=0:raise RuntimeError('SPATIAL_DECODER_INIT')

    def consume(self):
        while True:
            frame=Frame();self.init_frame(C.byref(frame));status=self.receive(self.handle,C.byref(frame))
            if status in (0,1,3):return
            if status!=2:raise RuntimeError('SPATIAL_UNSUPPORTED_JOC')
            if frame.format!=1 or frame.channels!=2 or frame.rate!=48000 or not 0<frame.length<=1048576 or frame.length!=frame.samples*8:
                raise RuntimeError('SPATIAL_PCM_FORMAT')
            if not self.confirmed:
                out=C.create_string_buffer(65536);required=C.c_size_t()
                if self.inspect(self.handle,out,len(out),C.byref(required))!=0 or json.loads(out.value).get('joc_present') is not True:
                    raise RuntimeError('SPATIAL_JOC_UNCONFIRMED')
                self.confirmed=True
            data=C.string_at(frame.data,frame.length);values=array.array('f');values.frombytes(data)
            if not all(map(math.isfinite,values)):raise RuntimeError('SPATIAL_PCM_INVALID')
            self.output(data,frame.samples)

    def feed(self,pointer,size):
        status=self.send(self.handle,pointer,size,-(1<<63),0)
        if status==4:self.consume();status=self.send(self.handle,pointer,size,-(1<<63),0)
        if status not in (0,1,2):raise RuntimeError('SPATIAL_UNSUPPORTED_JOC')
        self.consume()

    def finish(self):
        if self.drain(self.handle) not in (0,1,2,3,4):raise RuntimeError('SPATIAL_RENDER_FAILED')
        self.consume()

    def close(self):
        if self.handle:self.destroy(self.handle);self.handle=None
