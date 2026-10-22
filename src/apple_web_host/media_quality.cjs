/* Decoder metadata only. No network inspection, media URLs, headers or keys. */
'use strict';
const codecs=new Set(['aac','opus','vorbis','mp3','flac','alac','pcm','ac3','eac3']);
const number=(value,min,max)=>Number.isFinite(Number(value))&&Number(value)>=min&&Number(value)<=max?Number(value):0;
function audioConfig(value) {
  if(!value||typeof value!=='object')return {};
  const codec=String(value.codec||'').toLowerCase();
  if(!codecs.has(codec))return {};
  // A decoder's float32/sample-format is not the original recording's bit depth.
  return {codec,sampleRate:number(value['samples per second'],8000,768000),
    channels:number(value.channels,1,32),evidence:'decoder'};
}
class MediaQuality {
  constructor(){this.reset();}
  reset(){this.players=new Map();this.active='';this.revision=0;this.lastSnapshot=0;
    this.identity='';this.bound='';this.after=0;}
  message(method,params={}) {
    if(!['Media.playerPropertiesChanged','Media.playerEventsAdded'].includes(method)||typeof params.playerId!=='string')return;
    const id=params.playerId;
    if(!this.players.has(id)) {
      if(this.players.size>=32){const oldest=this.players.keys().next().value;this.players.delete(oldest);if(this.active===oldest)this.active='';}
      this.players.set(id,{quality:{},revision:0,hasAudio:false,playing:false});
    }
    const player=this.players.get(id);
    if(method==='Media.playerPropertiesChanged') {
      for(const p of (params.properties||[]).slice(0,100)) {
        if(p.name!=='kAudioTracks'||typeof p.value!=='string'||p.value.length>32000)continue;
        try {
          const tracks=JSON.parse(p.value);
          player.hasAudio=Array.isArray(tracks)&&tracks.length>0;
          player.quality=Array.isArray(tracks)&&tracks.length===1?audioConfig(tracks[0]):{};
          player.revision=++this.revision;
        }catch{player.quality={};player.hasAudio=false;}
      }
    } else for(const event of (params.events||[]).slice(0,100)) {
      if(typeof event.value!=='string'||event.value.length>32000)continue;
      let value;try{value=JSON.parse(event.value);}catch{continue;}
      if(value.event==='kLoad') {
        player.quality={};player.hasAudio=false;player.playing=false;player.revision=++this.revision;
        if(this.active===id)this.active='';
      }
      if(value.event==='kPlay'){player.playing=true;player.revision=++this.revision;}
      if(value.event==='kPause')player.playing=false;
      if(['kEnded','kWebMediaPlayerDestroyed'].includes(value.event)) {
        player.playing=false;
        if(this.active===id)this.active='';
        if(value.event==='kWebMediaPlayerDestroyed')this.players.delete(id);
      }
    }
    const audible=[...this.players].filter(([_id,p])=>p.hasAudio&&p.playing);
    const next=audible.length===1?audible[0][0]:audible.length>1?'':this.active;
    if(next!==this.active) {
      this.active=next;
      if(this.players.has(next))this.players.get(next).revision=++this.revision;
    }
  }
  snapshot(identity) {
    const player=this.players.get(this.active);
    if(identity!==this.identity) {
      this.identity=identity;this.bound='';this.after=this.lastSnapshot;
    }
    // A new song must have a fresh play/configuration event. Prefetched players
    // never override the player that actually received kPlay.
    if(identity&&player&&player.revision>this.after)this.bound=this.active;
    this.lastSnapshot=this.revision;
    return identity&&this.bound===this.active&&player?{...player.quality}:{};
  }
}
function attach(contents) {
  const tracker=new MediaQuality(),debugger_=contents.debugger;
  if(!debugger_)return tracker;
  try {
    debugger_.attach('1.3');
    debugger_.on('message',(_e,method,params)=>tracker.message(method,params));
    debugger_.on('detach',()=>tracker.reset());
    contents.on('did-start-navigation',(_e,_url,inPlace,main)=>{if(main&&!inPlace)tracker.reset();});
    debugger_.sendCommand('Media.enable').catch(()=>tracker.reset());
  }catch{} // Unsupported engines keep playing and report unknown quality.
  return tracker;
}
module.exports={MediaQuality,audioConfig,attach};
