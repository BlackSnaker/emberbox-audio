'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm');
const {validateEQ,installEQ,validatePoint}=require('../src/apple_web_host/flow_eq.cjs');
const {FlowDecks,mixCurve}=require('../src/apple_web_host/flow.cjs');

function context(rate=48000){
 const nodes=[];
 const parameter=initial=>({value:initial,curve:null,hold:null,ramp:null,
  cancelScheduledValues(){this.curve=null;},
  setValueCurveAtTime(v,start,duration){this.curve={v,start,duration};},
  cancelAndHoldAtTime(at){this.hold=at;},linearRampToValueAtTime(value,at){this.ramp={value,at};}});
 const node=(kind)=>{const n={kind,links:[],gain:parameter(kind==='gain'?1:0),connect(other){this.links.push(other);},disconnect(other){this.links=this.links.filter(v=>v!==other);}};nodes.push(n);return n;};
 const c={sampleRate:rate,currentTime:0,createGain:()=>node('gain'),
  createIIRFilter(b,a){const n=node('iir');n.b=b;n.a=a;return n;},getOutputTimestamp:()=>({contextTime:0,performanceTime:0})};
 return {context:c,source:node('source'),gain:node('output'),nodes,stop(){this.stopped=true;}};
}

function value(parameter,t){
 if(!parameter.curve)return parameter.value;
 const {v,start,duration}=parameter.curve,x=Math.max(0,Math.min(v.length-1,(t-start)/duration*(v.length-1))),at=Math.floor(x);
 return v[at]+(v[Math.min(v.length-1,at+1)]-v[at])*(x-at);
}

async function run(){
 assert.equal(validateEQ(null),null);
 assert.deepEqual(validatePoint(null),[.5,.5]);
 for(const p of [[0,.5],[.5,1],[NaN,.5],{},[.5]])assert.throws(()=>validatePoint(p),/INVALID_ARGUMENTS/);
 for(const eq of [{out:[1,0,0],in:[0,0,0]},{out:[-13,0,0],in:[0,0,0]},{out:[NaN,0,0],in:[0,0,0]},{out:[],in:[]}])assert.throws(()=>validateEQ(eq),/INVALID_ARGUMENTS/);
 const original={out:[-9,0,0],in:[-6,0,0]},copy=validateEQ(original);copy.out[0]=0;assert.equal(original.out[0],-9);
 for(const rate of [48000,192000]){
  const g=context(rate);g.source.connect(g.gain);const eq=installEQ(g);assert.equal(installEQ(g),eq);
  assert(!g.source.links.includes(g.gain),'Dry source bypassed the EQ routing');
  assert.equal(g.nodes.filter(n=>n.kind==='iir').length,2);
  const reserve=eq.schedule([-9,-3,0],true,2,4);assert(reserve>=1);
  const gains=g.nodes.filter(n=>n.kind==='gain');
  assert.equal(value(gains[0].gain,6),1);assert.equal(value(gains[1].gain,6),0);assert.equal(value(gains[2].gain,6),0);
  // The graph is an exact dry signal at the end, with no graph reconnection.
  g.context.currentTime=3;eq.release();
  gains.forEach((n,i)=>{assert.equal(n.gain.hold,3);assert.deepEqual(n.gain.ramp,{value:i===0?1:0,at:3.08});});
 }
 // Exercise the actual page-injection method and shared output-clock schedule.
 const graph=context();graph.source.connect(graph.gain);
 class Media{get volume(){return this.level??1;}set volume(v){this.level=v;}addEventListener(){}}
 const media=graph.media=new Media();
 const page={isDestroyed:()=>false,webContents:{executeJavaScript:code=>Promise.resolve(vm.runInNewContext(code,
  {window:{__emberFlowAudio:graph,__emberFlowMedia:media},HTMLMediaElement:Media,clearInterval(){},performance:{timeOrigin:1000},Math,Float32Array,Error}))}};
 const flow=new FlowDecks(page,()=>{throw Error('Unexpected renderer');},null,'');flow.beatSync=false;
 await flow.equalize(page,[-6,0,0],true,1500,4);
 assert.equal(graph.nodes.filter(n=>n.kind==='gain')[0].gain.curve.start,.5);assert(graph.stopped);
 await flow.gain(page,1,30,0,1500,'custom',[.3,.8]);
 for(let i=0;i<=1024;i++)assert(Math.abs(graph.gain.gain.curve.v[i]-mixCurve(i/1024,'custom',[.3,.8]))<1e-7);
 assert.equal(graph.gain.gain.curve.duration,30);
 await assert.rejects(flow.prepare({kind:'songs',id:'123',key:'test',eq:{out:[99,0,0],in:[0,0,0]}}),/INVALID_ARGUMENTS/);
 console.log('PASS transition EQ validation, complementary graph, bounded curves, dry release and shared audio clock');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
