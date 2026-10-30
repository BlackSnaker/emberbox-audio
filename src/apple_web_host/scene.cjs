'use strict';
const fs=require('node:fs'),path=require('node:path');
const modes=new Set(['auto','speakers','headphones']);
const codecs=new Set(['sbc','sbc_xq','aac','ldac','aptx','aptx_hd','aptx_ll','aptx_adaptive','lc3','opus']);
const profileIds=new Set(require('./headphone_profiles.json').profiles.map(p=>p.id));
function headphones(p={}){
 if(!p||typeof p!=='object'||Array.isArray(p))throw Error('INVALID_ARGUMENTS');
 const v={profile:p.profile??'none',strength:p.strength??100,bass:p.bass??0,treble:p.treble??0,balance:p.balance??0,bypass:p.bypass??false};
 if(!profileIds.has(v.profile)||typeof v.bypass!=='boolean')throw Error('INVALID_ARGUMENTS');
 for(const [k,min,max] of [['strength',0,100],['bass',-4,4],['treble',-4,4],['balance',-20,20]])if(!Number.isInteger(v[k])||v[k]<min||v[k]>max)throw Error('INVALID_ARGUMENTS');
 return v;
}
function preference(p={}){let h;try{h=headphones(p.headphones);}catch{h=headphones();}
 return {mode:modes.has(p.mode)?p.mode:'auto',angle:[20,30,40].includes(p.angle)?p.angle:30,hrtf:p.hrtf===1?1:0,
  sofa:typeof p.sofa==='string'&&/^[a-f0-9]{64}$/.test(p.sofa)?p.sofa:'',headphones:h};}
function signature(p){return p.mode==='speakers'?'speakers:'+p.angle:'headphones:'+(p.sofa||p.hrtf);}
class Scenes{
 constructor(file){
  this.file=file;this.enabled=false;this.base=preference();this.devices=new Map();this.output={};
  try{if(fs.statSync(file).size>32768)return;
   const value=JSON.parse(fs.readFileSync(file,'utf8'));this.enabled=value.enabled===true;this.base=preference(value.scene);
   for(const [key,p] of Object.entries(value.devices||{}).slice(-32))if(/^[a-f0-9]{32}$/.test(key))this.devices.set(key,preference(p));
  }catch{}
 }
 selected(){return this.devices.get(this.output.key)||this.base;}
 render(){const p=this.selected();return {...p,mode:p.mode==='auto'?(this.output.kind==='speakers'?'speakers':'headphones'):p.mode};}
 snapshot(){return {...this.render(),preference:this.selected().mode,device:this.output.label||'',bluetooth:this.output.bluetooth===true,
  codec:this.output.codec||'',outputRate:this.output.rate||0};}
 set(p){
  if(!modes.has(p.mode)||p.angle!==undefined&&![20,30,40].includes(p.angle)||p.hrtf!==undefined&&![0,1].includes(p.hrtf)||p.sofa!==undefined&&!(p.sofa===''||typeof p.sofa==='string'&&/^[a-f0-9]{64}$/.test(p.sofa)))throw Error('INVALID_ARGUMENTS');
  if(p.sofa){
   const root=path.join(path.dirname(this.file),'hrtf'),file=path.join(root,p.sofa+'.sofa');
   if(!fs.statSync(file).isFile()||fs.statSync(file).size>32*1024*1024)throw Error('INVALID_ARGUMENTS');
  }
  const value={...this.selected(),mode:p.mode,...(p.angle!==undefined?{angle:p.angle}:{}),...(p.hrtf!==undefined?{hrtf:p.hrtf,sofa:''}:{}),
   ...(p.sofa!==undefined?{sofa:p.sofa}:{}),...(p.headphones!==undefined?{headphones:headphones(p.headphones)}:{})};
  if(this.output.key){this.devices.delete(this.output.key);this.devices.set(this.output.key,value);while(this.devices.size>32)this.devices.delete(this.devices.keys().next().value);}
  else this.base=value;
  this.save(this.enabled);
 }
 setOutput(p){
  if(!/^[a-f0-9]{32}$/.test(p.key)||!['speakers','headphones','unknown'].includes(p.kind)||typeof p.label!=='string'||p.label.length>120||/[\x00-\x1f\x7f]/.test(p.label))throw Error('INVALID_ARGUMENTS');
  this.output={key:p.key,kind:p.kind,label:p.label,bluetooth:p.bluetooth===true,codec:codecs.has(p.codec)?p.codec:'',rate:Number.isInteger(p.rate)&&p.rate>=8000&&p.rate<=384000?p.rate:0};
  // A choice made before the first output probe belongs to that device,
  // rather than forcing its speaker/headphone mode onto all future devices.
  if(!this.devices.size&&(this.base.mode!=='auto'||this.base.sofa||JSON.stringify(this.base.headphones)!==JSON.stringify(headphones()))){
   this.devices.set(p.key,this.base);this.base=preference();this.save(this.enabled);
  }
 }
 save(enabled){
  this.enabled=enabled;
  if(!this.file)return;
  fs.mkdirSync(path.dirname(this.file),{recursive:true,mode:0o700});
  fs.writeFileSync(this.file+'.tmp',JSON.stringify({enabled,scene:this.base,devices:Object.fromEntries(this.devices)}),{mode:0o600});
  fs.renameSync(this.file+'.tmp',this.file);
 }
}
module.exports={Scenes,signature};
