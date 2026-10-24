"""Local intent interpretation through Ollama or an app-owned llama.cpp helper.

Only the user's wish and the preceding intent enter the language model. Music
catalogue data, listening history, account tokens and PCM are never submitted.
"""
import json,os,secrets,socket,subprocess,threading,time,urllib.request
from dj_intent import Intent,SCHEMA,SYSTEM,local_intent,model_intent,quick_wish
from dj_setup import ROOT,MODEL_NAME,ready


def request_json(url,data=None,timeout=3,token=''):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request(url,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,headers=headers)
    with urllib.request.urlopen(request,timeout=timeout) as response:
        raw=response.read(500001)
    if len(raw)>500000:raise ValueError('Local model response too large')
    return json.loads(raw)


class LocalBrain:
    def __init__(self):
        self.process=None;self.url='';self.token='';self.lock=threading.Lock();self.closed=False;self.last_use=time.monotonic()

    def models(self):
        try:
            data=request_json('http://127.0.0.1:11434/api/tags',timeout=1)
            return [str(x['name'])[:100] for x in data.get('models',[])[:40] if isinstance(x,dict) and x.get('name')
                    and 0<int(x.get('size',0))<4_000_000_000 and 'embed' not in x['name'].casefold()]
        except (OSError,ValueError,KeyError):return []

    def native(self,alive):
        with self.lock:
            if self.closed or not alive():raise InterruptedError('cancelled')
            if self.process and self.process.poll() is None:return self.url,self.token
            if not ready('brain'):raise RuntimeError('DJ brain is not installed')
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            self.token=secrets.token_urlsafe(24);self.url=f'http://127.0.0.1:{port}'
            self.process=subprocess.Popen([str(ROOT/'llama/llama-server'),'-m',str(ROOT/MODEL_NAME),
                '--host','127.0.0.1','--port',str(port),'--api-key',self.token,'--no-webui','--log-disable',
                '--ctx-size','2048','--threads','2','--threads-batch','2','--parallel','1','--n-gpu-layers','0'],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        until=time.monotonic()+8
        while time.monotonic()<until and alive() and not self.closed:
            if self.process.poll() is not None:raise RuntimeError('Local model runtime could not start')
            try:
                if request_json(self.url+'/health',timeout=1,token=self.token).get('status')=='ok':return self.url,self.token
            except (OSError,ValueError):pass
            time.sleep(.1)
        if not alive() or self.closed:raise InterruptedError('cancelled')
        raise RuntimeError('Local model preparation timed out')

    def interpret(self,prompt,previous=None,enabled=True,model='qwen2.5:1.5b',alive=lambda:True):
        self.last_use=time.monotonic()
        fallback=local_intent(prompt,previous)
        if not alive():raise InterruptedError('cancelled')
        if fallback.action!='mix' or not enabled or quick_wish(prompt):return fallback,'local'
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({
            'previous':(previous or Intent()).data(),'wish':str(prompt)[:500]},ensure_ascii=False)}]
        try:
            models=self.models()
            if not alive():raise InterruptedError('cancelled')
            if models:
                chosen=model if model in models else next((m for m in models if m.startswith(('qwen2.5:1.5b','qwen3:1.7b'))),models[0])
                data=request_json('http://127.0.0.1:11434/api/chat',{'model':chosen,'messages':messages,
                    'stream':False,'format':SCHEMA,'keep_alive':'45s','think':False,
                    'options':{'num_ctx':2048,'num_predict':220,'num_thread':2,'temperature':.15}},timeout=8)
                content=data.get('message',{}).get('content','')
            else:
                url,token=self.native(alive)
                data=request_json(url+'/v1/chat/completions',{'messages':messages,'stream':False,
                    'response_format':{'type':'json_object','schema':SCHEMA},'max_tokens':220,'temperature':.15},timeout=8,token=token)
                content=data.get('choices',[{}])[0].get('message',{}).get('content','')
            if not alive():raise InterruptedError('cancelled')
            parsed=json.loads(content)
            return model_intent(parsed,fallback,prompt),'ai'
        except InterruptedError:raise
        except (OSError,ValueError,KeyError,IndexError,TypeError,RuntimeError):return fallback,'local'

    def park(self):
        with self.lock:process,self.process=self.process,None
        if process and process.poll() is None:
            process.terminate()
            def reap():
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            threading.Thread(target=reap,daemon=True,name='ember-dj-brain-cleanup').start()

    def close(self):self.closed=True;self.park()
