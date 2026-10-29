"""Read only Ember's current output; never change routes or Bluetooth profiles."""
import hashlib,json,re,subprocess
from stream_target import Target,matches


def classify(sink):
    p=sink.get('properties') or {}
    port=next((v for v in sink.get('ports',[]) if v.get('name')==sink.get('active_port')),{})
    form=str(p.get('device.form_factor') or p.get('device.form-factor') or '').lower()
    port_type=str(port.get('type') or '').lower()
    if port_type in ('headphones','headset') or form in ('headphone','headset'):kind='headphones'
    elif port_type in ('speaker','lineout') or form in ('speaker','hifi','computer','tv'):kind='speakers'
    else:kind='unknown'
    spec=str(sink.get('sample_specification') or '')
    rate=re.search(r'\b(\d{4,6})Hz\b',spec)
    label=str(sink.get('description') or p.get('device.description') or 'Audio output')
    if label=='(null)':label='Audio output'
    label=re.sub(r'[\x00-\x1f\x7f]','',label)[:120]
    return {'key':hashlib.sha256(str(sink['name']).encode()).hexdigest()[:32],
            'kind':kind,'label':label,'bluetooth':p.get('device.bus')=='bluetooth',
            'codec':str(p.get('api.bluez5.codec') or '')[:32],
            'rate':int(rate.group(1)) if rate else 0}


def inspect_output(pid):
    def query(*args):
        result=subprocess.run(['pactl',*args],capture_output=True,text=True,timeout=1.5,check=True)
        if len(result.stdout)>2_000_000:raise ValueError('Audio graph too large')
        return result.stdout
    sinks=json.loads(query('-f','json','list','sinks'))
    streams=json.loads(query('-f','json','list','sink-inputs'))
    target=Target(source='apple-music',pid=pid,player='apple-native')
    matching=[s for s in streams if matches(s.get('properties',{}),target)]
    active=[s for s in matching if s.get('corked') is not True]
    owned={str(s['sink']) for s in active or matching}
    # An ambiguous/processed route must not choose another application's sink.
    if len(owned)>1:return None
    sink=next((s for s in sinks if str(s['index']) in owned),None)
    if sink is None:
        default=query('get-default-sink').strip();sink=next((s for s in sinks if s['name']==default),None)
    return classify(sink) if sink and not str(sink['name']).startswith(('emberbox_karaoke_','emberbox-karaoke-')) else None
