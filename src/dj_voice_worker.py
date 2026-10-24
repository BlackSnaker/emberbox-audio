"""Isolated speech helper. Microphone PCM is decoded in memory and never saved."""
import argparse,array,json,math,os,select,signal,subprocess,sys,tempfile,time,wave
from pathlib import Path

STOP=False
def stop(*_args):
    global STOP
    STOP=True
signal.signal(signal.SIGTERM,stop)


def emit(event,**values):print(json.dumps({'event':event,**values},ensure_ascii=False),flush=True)


def reap(process):
    if process.poll() is None:process.terminate()
    try:process.wait(timeout=1)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)


def recognize(root,language,audio=None):
    from vosk import Model,KaldiRecognizer,SetLogLevel
    SetLogLevel(-1)
    recognizer=KaldiRecognizer(Model(str(root/('asr-'+language))),16000)
    if audio:
        # Offline verification path; production capture never writes a WAV.
        with wave.open(audio,'rb') as source:
            if source.getframerate()!=16000 or source.getnchannels()!=1 or source.getsampwidth()!=2:raise ValueError('Expected mono 16 kHz PCM')
            pieces=[]
            while data:=source.readframes(4096):
                if recognizer.AcceptWaveform(data):pieces.append(json.loads(recognizer.Result()).get('text',''))
            pieces.append(json.loads(recognizer.FinalResult()).get('text',''))
        emit('result',text=' '.join(p for p in pieces if p));return
    if STOP:return
    properties='{ application.name = "Ember DJ Microphone" media.role = "Communication" }'
    process=subprocess.Popen(['pw-record','--raw','--format','s16','--rate','16000','--channels','1',
        '-P',properties,'-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
    emit('listening');started=time.monotonic();last_partial='';last_voice=started;pieces=[];heard=False;last_meter=0.
    try:
        while not STOP and time.monotonic()-started<15:
            readable,_,_=select.select([process.stdout,sys.stdin],[],[],.1)
            if sys.stdin in readable:sys.stdin.readline();break
            if process.stdout not in readable:
                if process.poll() is not None:raise RuntimeError('microphone-unavailable')
                continue
            data=os.read(process.stdout.fileno(),4096)
            if not data:raise RuntimeError('microphone-unavailable')
            samples=array.array('h');samples.frombytes(data[:len(data)//2*2])
            level=math.sqrt(sum(v*v for v in samples)/max(1,len(samples)))/32768
            now=time.monotonic()
            if level>.012:heard=True;last_voice=now
            if now-last_meter>.12:emit('level',value=min(1,level*8));last_meter=now
            if recognizer.AcceptWaveform(data):
                text=json.loads(recognizer.Result()).get('text','')
                if text:pieces.append(text)
            else:
                partial=json.loads(recognizer.PartialResult()).get('partial','')
                if partial and partial!=last_partial:emit('partial',text=' '.join(pieces+[partial]));last_partial=partial
            if heard and (pieces or last_partial) and now-last_voice>1.25:break
        text=json.loads(recognizer.FinalResult()).get('text','')
        if text:pieces.append(text)
        emit('result',text=' '.join(p for p in pieces if p)[:500])
    finally:reap(process)


def write_pcm(audio,output):
    import torch
    # The model returns inference tensors. Copy before applying edge fades
    # outside InferenceMode; otherwise newer PyTorch rejects in-place writes.
    audio=audio.detach().cpu().flatten().clone()
    if audio.numel()<2 or not torch.isfinite(audio).all():raise ValueError('voice-audio-invalid')
    peak=float(audio.abs().max())
    if peak>.94:audio*=.94/peak
    fade=min(576,audio.numel()//2)
    audio[:fade]*=torch.linspace(0,1,fade);audio[-fade:]*=torch.linspace(1,0,fade)
    pcm=array.array('h',(audio*32767).round().to(torch.int16).tolist())
    if sys.byteorder!='little':pcm.byteswap()
    with wave.open(str(output),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(pcm.tobytes())


def synthesize(root,language,text,output):
    if language=='ru':
        import hashlib
        # A torch package contains executable model code: verify the pinned
        # publisher asset before importing it, including after installation.
        path=root/'silero-v5_5_ru.pt'
        if path.stat().st_size!=145420684:raise ValueError('voice-model-invalid')
        digest=hashlib.sha256()
        with path.open('rb') as source:
            while chunk:=source.read(1024*1024):
                if STOP:return
                digest.update(chunk)
        if digest.hexdigest()!='50081637b602126ee06cb3bc8a744d25651d2da149ee8864b9a379bfdd934437':raise ValueError('voice-model-invalid')
        import torch
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        model=torch.package.PackageImporter(str(path)).load_pickle('tts_models','model');model.to(torch.device('cpu'))
        if STOP:return
        with torch.inference_mode():
            audio=model.apply_tts(text=str(text)[:500],speaker='kseniya',sample_rate=48000,put_accent=True,put_yo=True)
        write_pcm(audio,output)
        return
    voice='en_US-ljspeech-medium'
    command=[str(root/'piper/piper'),'-m',str(root/(voice+'.onnx')),'-f',str(output),
        '--length_scale','1.02','--sentence_silence','0.12']
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        process.communicate((str(text)[:500]+'\n').encode(),timeout=25)
        if process.returncode:raise RuntimeError('voice-synthesis-failed')
    finally:reap(process)


def speak(root,language,text,output=None):
    with tempfile.TemporaryDirectory(prefix='speech-',dir=root) as temporary:
        destination=Path(output) if output else Path(temporary)/'reply.wav'
        destination.touch(mode=0o600);synthesize(root,language,text,destination)
        if output:emit('result',path=str(destination));return
        if STOP:return
        emit('speaking')
        properties='{ application.name = "Ember DJ Voice" media.role = "Communication" }'
        player=subprocess.Popen(['pw-play','--volume','.8','-P',properties,str(destination)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            while player.poll() is None and not STOP:time.sleep(.05)
            if player.poll() not in (None,0) and not STOP:raise RuntimeError('voice-playback-failed')
        finally:reap(player)
        emit('finished')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('listen','speak'))
    parser.add_argument('--root',required=True);parser.add_argument('--language',choices=('ru','en'),default='ru')
    parser.add_argument('--input');parser.add_argument('--output');args=parser.parse_args()
    try:
        os.nice(5)
        # Keep recognition and synthesis away from an all-core burst. Children
        # inherit the two-CPU budget; the GTK process keeps its normal affinity.
        if hasattr(os,'sched_getaffinity'):
            allowed=sorted(os.sched_getaffinity(0))
            if allowed:os.sched_setaffinity(0,set(allowed[-2:]))
        os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='1'
        os.environ['MKL_NUM_THREADS']='2'
        root=Path(args.root)
        if args.mode=='listen':recognize(root,args.language,args.input)
        else:
            request=json.loads(sys.stdin.readline());speak(root,args.language,request.get('text',''),args.output)
    except Exception as error:emit('error',message=str(error)[:150]);sys.exit(1)
