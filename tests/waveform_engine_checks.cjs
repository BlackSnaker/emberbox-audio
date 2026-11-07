'use strict';
const assert=require('node:assert/strict');
const {Waveforms}=require('../src/apple_web_host/waveforms.cjs');
function owner(){
 const requests=[],children=[];
 const o={generation:0,session:{rate:48000},scenes:{render:()=>({mode:'speakers',angle:30})},requests,children,
  source:async(win,p)=>{requests.push(p);return p.action==='prepare'?{contextId:'analysis-'+requests.length,metadata:{duration:180}}:{};},
  spawn:()=>{const c={killed:false,kill(){this.killed=true;},pid:0};children.push(c);return c;},
  wire:(c,message,failed)=>{c.message=message;c.failed=failed;},send:(c,p)=>c.command=p};return o;
}
const parameters={operation:'waveform-start',key:'a'.repeat(32),kind:'songs',id:'123',role:'out',seconds:32};
async function run(){
 const o=owner(),w=new Waveforms(o);
 assert.deepEqual(w.command({},parameters,{decoder:'fixture'}),{accepted:true});await new Promise(setImmediate);
 const child=o.children[0];assert(child);assert.equal(child.command.position,148);assert(child.command.waveform);assert.equal(child.command.pcm,undefined);
 const context=o.requests[0];assert.equal(context.waveform,true);
 child.message({type:'waveform',waveform:{evidence:'decoded-pcm',bins:[[-.5,.5,.2]],start:148,seconds:32,covered:32,step:32,rate:48000}});
 const status=w.command({}, {operation:'waveform-status',key:parameters.key});assert.equal(status.phase,'ready');assert(child.killed);
 assert(o.requests.some(p=>p.action==='close'&&p.contextId.startsWith('analysis-')));
 assert(!o.requests.some(p=>['play','seek','transport'].includes(p.action)));
 w.cancel();
 const blocked=owner();blocked.session.manual={id:'playing'};
 assert.throws(()=>new Waveforms(blocked).command({},parameters,{}),/SPATIAL_BUSY/);
 const pending=owner();let release;pending.source=async(_win,p)=>p.action==='prepare'?await new Promise(r=>release=r):{};
 const cancelled=new Waveforms(pending);cancelled.command({},parameters,{});cancelled.cancel();
 release({contextId:'late',metadata:{duration:180}});await new Promise(setImmediate);assert.equal(pending.children.length,0);
 console.log('PASS measured waveform job isolation, exact outro position, no playback commands and stale cancellation');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
