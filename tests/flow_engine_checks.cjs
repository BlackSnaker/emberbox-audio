'use strict';
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {FlowDecks}=require('../src/apple_web_host/flow.cjs');

async function cancellation() {
 let release,entered;const started=new Promise(r=>entered=r),wait=new Promise(r=>release=r),calls=[];
 const window=()=>({dead:false,isDestroyed(){return this.dead;},destroy(){this.dead=true;},webContents:{executeJavaScript:async()=>true}});
 const a=window(),b=window();
 const request=async(w,r)=>{calls.push([w,r.method,r.params?.action]);
  if(r.method==='status')return {duration:180,position:100};
  if(w===b&&r.params?.action==='resume'){entered();await wait;}return {};};
 const flow=new FlowDecks(a,()=>b,request,'https://music.apple.com');
 flow.next=b;flow.key='entry';flow.holdTail=flow.startMuted=async()=>true;
 flow.inspect=async()=>({playing:true,time:2});flow.gain=async()=>true;
 const result=flow.transition({key:'entry',duration:4}).catch(e=>e.message);
 await started;await flow.cancel();release();assert.equal(await result,'FLOW_CANCELLED');
 assert(!calls.some(([w,m,action])=>w===a&&m==='transport'&&action==='resume'),'Cancel resumed the user-paused track');
 assert(!a.dead&&b.dead);
}

async function envelope() {
 let now=0,tick=null,physical=1,logical=1,guard=null;
 class Node{};class Media extends Node{};
 Object.defineProperty(Media.prototype,'volume',{get(){return physical;},set(v){physical=v;
  let stopped=false;guard?.({stopImmediatePropagation(){stopped=true;}});if(!stopped)logical=v;}});
 const media=new Media();media.paused=false;media.ended=false;media.currentTime=10;
 media.addEventListener=(name,fn)=>{if(name==='volumechange')guard=fn;};media.removeEventListener=()=>guard=null;
 const root={_services:{playback:{_currentPlayer:{_targetElement:media}}}};
 const sandbox={window:{MusicKit:{getInstance:()=>root}},HTMLMediaElement:Media,Node,
  performance:{now:()=>now},setInterval:fn=>(tick=fn,1),clearInterval:()=>tick=null,Map,Set,Object,Number,Math};
 const page={isDestroyed:()=>false,webContents:{executeJavaScript:code=>Promise.resolve(vm.runInNewContext(code,sandbox))}};
 const flow=new FlowDecks(page,null,null,null);
 await flow.gain(page,0,4,1);now=2000;tick();
 assert(Math.abs(physical-.5)<1e-9);assert.equal(media.volume,1);assert.equal(logical,1,'The fade rewrote MusicKit logical volume');
 media.volume=.6;tick();assert(Math.abs(physical-.3)<1e-9,'A source-volume change lost its envelope');
 await flow.cancel();assert.equal(physical,.6);assert.equal(media.volume,.6);assert(!guard);
}

(async()=>{await cancellation();await envelope();console.log('PASS Apple cancellation, headroom envelope and logical-volume isolation');})()
 .catch(e=>{console.error(e);process.exitCode=1;});
