"""Local intent interpretation through Ollama or an app-owned llama.cpp helper.

Only the user's wish and the preceding intent enter the language model. Music
catalogue data, listening history, account tokens and PCM are never submitted.
"""
import json,logging,os,secrets,socket,subprocess,threading,time,urllib.request
import re
from pathlib import Path
from collections import OrderedDict
from dj_intent import local_intent,quick_wish,wish_text
from dj_semantics import SCHEMA,SYSTEM,decode,context,follows,clarify,vocal_followup
from dj_setup import ROOT,MODEL_NAME,ready
from source_picker import text


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
        self.cache=OrderedDict();self.available=threading.Event();self.failure=''

    def models(self):
        try:
            data=request_json('http://127.0.0.1:11434/api/tags',timeout=1)
            return [str(x['name'])[:100] for x in data.get('models',[])[:40] if isinstance(x,dict) and x.get('name')
                    and 0<int(x.get('size',0))<2_500_000_000 and 'embed' not in x['name'].casefold()]
        except (OSError,ValueError,KeyError):return []

    def native(self,alive):
        with self.lock:
            if self.closed or not alive():raise InterruptedError('cancelled')
            if not self.process or self.process.poll() is not None:
                if not ready('brain'):raise RuntimeError('DJ brain is not installed')
                self.available.clear()
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                self.token=secrets.token_urlsafe(24);self.url=f'http://127.0.0.1:{port}'
                self.process=subprocess.Popen([str(ROOT/'llama/llama-server'),'-m',str(ROOT/MODEL_NAME),
                    '--host','127.0.0.1','--port',str(port),'--api-key',self.token,'--no-webui','--log-disable',
                    '--ctx-size','1536','--threads','2','--threads-batch','2','--parallel','1','--n-gpu-layers','0',
                    '--threads-http','1','--reasoning','off','--reasoning-budget','0',
                    '--chat-template-kwargs','{"enable_thinking":false}'],
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            process,url,token=self.process,self.url,self.token
            if self.available.is_set():return url,token
        until=time.monotonic()+5
        while time.monotonic()<until and alive() and not self.closed:
            if self.process is not process:raise InterruptedError('Model unloaded')
            if process.poll() is not None:raise RuntimeError('Local model runtime could not start')
            try:
                if self.available.is_set() or request_json(url+'/health',timeout=1,token=token).get('status')=='ok':
                    self.available.set();return url,token
            except (OSError,ValueError):pass
            time.sleep(.1)
        if not alive() or self.closed:raise InterruptedError('cancelled')
        raise RuntimeError('Local model preparation timed out')

    def warm(self):
        if self.closed or not ready('brain'):return
        self.last_use=time.monotonic()
        try:self.native(lambda:not self.closed)
        except (OSError,ValueError,RuntimeError,InterruptedError):pass

    def generate(self,url,data,alive,budget=10,token=''):
        """Closing the child closes HTTP too; a canceled wish does not keep CPU work queued."""
        helper=Path(__file__).with_name('dj_model_client.py')
        process=subprocess.Popen([os.sys.executable,'-I',str(helper)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
        raw=json.dumps({'url':url,'data':data,'token':token}).encode();deadline=time.monotonic()+max(.05,budget)
        first=True
        try:
            while time.monotonic()<deadline:
                if self.closed or not alive():raise InterruptedError('cancelled')
                try:
                    stdout,_=process.communicate(input=raw if first else None,timeout=.05)
                    if process.returncode:raise RuntimeError('local-inference-failed')
                    if len(stdout)>500000:raise ValueError('Model response too large')
                    return json.loads(stdout)
                except subprocess.TimeoutExpired:first=False
            raise TimeoutError('Local interpretation timed out')
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=.3)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=.3)

    def interpret(self,prompt,previous=None,enabled=True,model='qwen3.5:2b',alive=lambda:True):
        started=self.last_use=time.monotonic();self.failure=''
        fallback=local_intent(prompt,previous)
        if not alive():raise InterruptedError('cancelled')
        if not re.search(r'\w',str(prompt)):return clarify(),'local'
        if previous is None and re.search(r'как раньше|как до этого|то же самое|в том же духе|same as before|the same',str(prompt),re.I):
            return clarify(),'local'
        vocal=vocal_followup(prompt,previous)
        if vocal is not None:return vocal,'local'
        if quick_wish(prompt,previous,fallback):return fallback,'local'
        if not enabled:return clarify(text('Enable free-form wishes in DJ settings, or name a mood, artist or song.',
            'Включи свободные пожелания в настройках DJ или уточни настроение, исполнителя либо песню.')),'disabled'
        preceding=previous if follows(prompt) else None
        fallback=local_intent(prompt,preceding)
        key=(wish_text(prompt).casefold(),json.dumps(context(preceding),sort_keys=True),model)
        cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<600:
            self.cache.move_to_end(key);return cached[1],'ai'
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({
            'previous':context(preceding),'wish':str(prompt)[:500],
            'language':'ru' if re.search('[А-Яа-яЁё]',str(prompt)) else 'en'},ensure_ascii=False)}]
        try:
            if not alive():raise InterruptedError('cancelled')
            if ready('brain'):
                url,token=self.native(alive)
                data=self.generate(url+'/v1/chat/completions',{'messages':messages,'stream':False,
                    'response_format':{'type':'json_object','schema':SCHEMA},'max_tokens':48,'temperature':0},alive,
                    budget=min(10,12-(time.monotonic()-started)),token=token)
                content=data.get('choices',[{}])[0].get('message',{}).get('content','')
            else:
                models=self.models()
                if not models:return clarify(text('Prepare local AI in DJ settings to understand this wish.',
                    'Подготовь локальный ИИ в настройках DJ — он поможет понять это пожелание.')),'needs-model'
                chosen=model if model in models else next((m for m in models if m.startswith(('qwen3.5:2b','qwen3:1.7b'))),models[0])
                data=self.generate('http://127.0.0.1:11434/api/chat',{'model':chosen,'messages':messages,
                    'stream':False,'format':SCHEMA,'keep_alive':'30s','think':False,
                    'options':{'num_ctx':1536,'num_predict':48,'num_thread':2,'temperature':0}},alive,
                    budget=min(10,12-(time.monotonic()-started)))
                content=data.get('message',{}).get('content','')
            if not alive():raise InterruptedError('cancelled')
            intent=decode(json.loads(content),prompt,preceding,fallback)
            self.cache[key]=(time.monotonic(),intent)
            while len(self.cache)>64:self.cache.popitem(last=False)
            return intent,'ai'
        except InterruptedError:raise
        except (OSError,ValueError,KeyError,IndexError,TypeError,RuntimeError) as error:
            self.failure=type(error).__name__+': '+str(error)[:100]
            logging.getLogger(__name__).warning('Local DJ interpretation unavailable (%s)',self.failure)
            return clarify(text('I could not confidently interpret that. What sound or mood matters most?',
                'Не уверена, что правильно поняла. Какое звучание или настроение здесь главное?')),'uncertain'

    def park(self):
        with self.lock:process,self.process=self.process,None;self.available.clear()
        if process and process.poll() is None:
            process.terminate()
            def reap():
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            threading.Thread(target=reap,daemon=True,name='ember-dj-brain-cleanup').start()

    def close(self):self.closed=True;self.park()
