"""Optional, isolated Android FairPlay session. Native contexts remain opaque."""
import ctypes as C
import hashlib
import os
from pathlib import Path
import re


def bind(lib,name,result,*arguments):
    fn=getattr(lib,name);fn.restype=result;fn.argtypes=list(arguments);return fn


class FairPlay:
    def __init__(self,runtime):
        library=Path(runtime['library']);root=library.parent
        if hashlib.sha256(library.read_bytes()).hexdigest()!=runtime['librarySha256']:
            raise RuntimeError('SPATIAL_RUNTIME_CHANGED')
        profile=Path(runtime['profile'])
        if not profile.is_dir() or not (profile/'session-ready').is_file():
            raise RuntimeError('SPATIAL_FAIRPLAY_SIGN_IN_REQUIRED')
        device=(profile/'device-id').read_text().strip()
        if not re.fullmatch('[a-f0-9]{16}',device):raise RuntimeError('SPATIAL_RUNTIME_CHANGED')
        # This process never opens another application's profile or account.
        empty=root/'empty-home';empty.mkdir(mode=0o700,exist_ok=True)
        os.environ.update(HOME=str(empty),HYBRIS_LINKER_DIR=str(root/'linker'),
            HYBRIS_ANDROID_LIB64=str(root/'lib64'),HYBRIS_LD_LIBRARY_PATH=str(root/'lib64'))
        self.lib=C.CDLL(str(library));self.contexts={}
        load=bind(self.lib,'hybris_backend_init',C.c_int,*([C.c_char_p]*3))
        if load(str(root/'linker').encode(),str(root/'lib64').encode(),b'')!=0:
            raise RuntimeError('SPATIAL_FAIRPLAY_UNAVAILABLE')
        self.auth_type=C.CFUNCTYPE(None,C.c_char_p,C.c_void_p,C.c_int,C.c_void_p)
        @self.auth_type
        def deny_prompt(kind,output,size,userdata):
            if output and size>0:C.memset(output,0,size)
        self.auth=deny_prompt
        login=bind(self.lib,'hybris_fairplay_init',C.c_int,*([C.c_char_p]*5),self.auth_type,C.c_void_p)
        info=('Music/4.9/Android/10/Emberbox/1/en-US/en-US/'+device).encode()
        if login(str(profile).encode(),info,str(root/'lib64').encode(),None,None,self.auth,None)!=0:
            raise RuntimeError('SPATIAL_FAIRPLAY_SIGN_IN_REQUIRED')
        self.open_fn=bind(self.lib,'hybris_open_kd_ctx_from_uri',C.c_void_p,C.c_char_p,C.c_char_p,C.POINTER(C.c_uint))
        self.decrypt_fn=bind(self.lib,'hybris_backend_decrypt',C.c_int,C.c_void_p,C.c_uint,C.c_void_p,C.c_uint)

    def license(self,ident,uri):
        if not re.fullmatch(r'\d{1,20}',str(ident)) or not isinstance(uri,str) or len(uri)>512 or not re.fullmatch(r'skd://itunes\.apple\.com/[A-Za-z0-9/_=.-]+',uri):
            raise ValueError('Invalid FairPlay license identifier')
        owner='0' if '/P000000000/' in uri else str(ident)
        key=(owner,uri)
        if key not in self.contexts:
            if len(self.contexts)>=16:raise ValueError('FairPlay context limit')
            epoch=C.c_uint()
            handle=self.open_fn(owner.encode(),uri.encode(),C.byref(epoch))
            if not handle:raise RuntimeError('SPATIAL_LICENSE_REJECTED')
            self.contexts[key]=(handle,epoch.value)
        return self.contexts[key]

    def decode_sample(self,data,crypto,context,deliver):
        if not 0<len(data)<=1048576 or crypto.get('scheme')!=2 or crypto.get('skip')!=0 or crypto.get('iv_size')!=0:
            raise ValueError('Unsupported FairPlay audio encryption')
        pairs=crypto.get('pairs') or [(0,len(data))]
        if len(pairs)>1024 or sum(a+b for a,b in pairs)!=len(data) or any(a<0 or b<0 for a,b in pairs):
            raise ValueError('Invalid FairPlay subsamples')
        buffer=C.create_string_buffer(data,len(data));at=0
        for clear,encrypted in pairs:
            at+=clear;whole=encrypted&~15
            if whole and self.decrypt_fn(context[0],context[1],C.byref(buffer,at),whole)!=0:
                raise RuntimeError('SPATIAL_DECRYPT_FAILED')
            at+=encrypted
        deliver(buffer,len(data))

    def close(self):
        # Native lifetime, including its lease thread, is the worker lifetime.
        self.contexts.clear()
