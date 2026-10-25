"""Isolated native sign-in. Account data and vendor logs stay out of diagnostics."""
import ctypes as C,json,os,resource,sys,uuid,threading,re
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.umask(0o077)
if C.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError('DUMP_PROTECTION')
if C.CDLL(None).prctl(1,15,0,0,0)!=0:raise RuntimeError('PARENT_PROTECTION')
if os.getppid()==1:os._exit(1)
control=os.fdopen(os.dup(1),'w',buffering=1)
diag_read,diag_write=os.pipe()
with open(os.devnull,'wb') as quiet:os.dup2(quiet.fileno(),1)
os.dup2(diag_write,2);os.close(diag_write)
output_lock=threading.Lock()

def emit(**value):
 with output_lock:control.write(json.dumps(value)+'\n')
def diagnostics():
 stages={'[drm_lib] login failed':'login-rejected','[ember] authentication response absent':'auth-response-absent','[drm_lib] drm_init_ctx failed':'context-failed','[drm_lib] failed to get storefront ID':'storefront-failed','[drm_lib] failed to get dev token':'developer-token-failed','[drm_lib] failed to get music token':'music-token-failed','[ember] no auxiliary music token; testing DRM-only session':'drm-only-session','[guard] drm_lib_init: SVError escaped':'native-exception','[hybris] wrapper state: RUNNING':'native-running'}
 with os.fdopen(diag_read,'rb') as stream:
  while True:
   line=stream.readline(65537)
   if not line:return
   if len(line)>65536 or not line.endswith(b'\n'):continue
   value=line.decode('utf-8','replace').strip()
   if value in stages:emit(event='diagnostic',stage=stages[value])
   match=re.match(r'^\[!\] auth error: code=(-?\d+),',value)
   if match:emit(event='diagnostic',stage='apple-auth',code=int(match[1]))
   match=re.match(r'^\[!\] auth failed: response type (\d+)$',value)
   if match:emit(event='diagnostic',stage='auth-response',code=int(match[1]))
   if value.startswith('[guard] drm_lib_init exception:'):emit(event='diagnostic',stage='native-cpp-exception')
diagnostic_thread=threading.Thread(target=diagnostics,daemon=True);diagnostic_thread.start()
def read():
 line=sys.stdin.buffer.readline(8193)
 if not line or len(line)>8192:raise RuntimeError('CLOSED')
 return json.loads(line)

def main():
 from fairplay_setup import configured
 runtime=configured()
 if not runtime:raise RuntimeError('SETUP_REQUIRED')
 root=Path(runtime['library']).parent;profile=Path(runtime['profile']);profile.mkdir(mode=0o700,exist_ok=True)
 os.environ.update(HOME=str(root/'empty-home'),HYBRIS_LINKER_DIR=str(root/'linker'),HYBRIS_ANDROID_LIB64=str(root/'lib64'),HYBRIS_LD_LIBRARY_PATH=str(root/'lib64'))
 import hashlib
 if hashlib.sha256(Path(runtime['library']).read_bytes()).hexdigest()!=runtime['librarySha256']:raise RuntimeError('LOAD_FAILED')
 lib=C.CDLL(runtime['library'])
 load=lib.hybris_backend_init;load.argtypes=[C.c_char_p]*3;load.restype=C.c_int
 if load(str(root/'linker').encode(),str(root/'lib64').encode(),b'')!=0:raise RuntimeError('LOAD_FAILED')
 emit(event='ready')
 data=read()
 if data.get('action')!='login':return
 username=data.get('username','').encode();password=data.get('password','').encode()
 if username is not None and (not 1<=len(username)<=250 or not 1<=len(password)<=239):raise RuntimeError('INPUT_LENGTH')
 data.clear()
 AUTH=C.CFUNCTYPE(None,C.c_char_p,C.c_void_p,C.c_int,C.c_void_p)
 @AUTH
 def auth(kind,output,size,userdata):
  try:
   C.memset(output,0,size)
   if kind==b'credentials-requested':
    emit(event='credentials-requested')
    if username is not None:C.memmove(output,b'1',1)
    return
   if kind.startswith(b'dialog:'):
    payload=json.loads(kind[7:]);emit(event='dialog',dialog=payload)
    reply=read()
    index=reply.get('selection')
    if reply.get('action')=='dialog' and isinstance(index,int) and 0<=index<len(payload.get('buttons',[])):
     raw=str(index).encode();C.memmove(output,raw,min(len(raw),size-1))
    return
   if kind==b'dialog-required':emit(event='dialog-required');return
   if kind!=b'2fa':return
   emit(event='code-needed')
   reply=read();code=str(reply.get('code',''))
   if reply.get('action')=='code' and len(code)==6 and code.isascii() and code.isdigit():C.memmove(output,code.encode(),min(6,size-1))
  except Exception:pass
 device=profile/'device-id'
 if not device.exists():device.write_text(uuid.uuid4().hex[:16])
 info=('Music/4.9/Android/10/Emberbox/1/en-US/en-US/'+device.read_text().strip()).encode()
 login=lib.hybris_fairplay_init;login.argtypes=[C.c_char_p]*5+[AUTH,C.c_void_p];login.restype=C.c_int
 emit(event='authenticating')
 result=login(str(profile).encode(),info,str(root/'lib64').encode(),username,password,auth,None)
 password=None;username=None
 if result!=0:emit(event='sign-in-failed');return
 (profile/'session-ready').write_text('authenticated\n')
 (profile/'session-ready').chmod(0o600)
 emit(event='signed-in')

if __name__=='__main__':
 try:main()
 except Exception as error:emit(event='error',code=str(error) if str(error) in ('CLOSED','LOAD_FAILED','INPUT_LENGTH','SETUP_REQUIRED') else 'NATIVE_FAILED')
 finally:
  try:os.close(2)
  except OSError:pass
  diagnostic_thread.join(timeout=1);control.flush();os._exit(0)
