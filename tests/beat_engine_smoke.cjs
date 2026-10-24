'use strict';
// Standalone Electron fixture: generated clicks only, all output gains are zero.
const {app,BrowserWindow}=require('electron'),assert=require('node:assert/strict');
const {FlowDecks}=require('./flow.cjs'),{detectBeat,attachTap}=require('./rhythm.cjs');
app.commandLine.appendSwitch('autoplay-policy','no-user-gesture-required');
const delay=ms=>new Promise(r=>setTimeout(r,ms));let windows=[],failed=false;
async function deck(bpm,phase){
 const w=new BrowserWindow({show:false,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});windows.push(w);
 await w.loadURL('data:text/html,<title>Ember generated beat check</title>');
 await w.webContents.executeJavaScript(`(async()=>{const rate=48000,n=rate*18,buffer=new ArrayBuffer(44+n*4),v=new DataView(buffer),s=(at,text)=>{for(let i=0;i<text.length;i++)v.setUint8(at+i,text.charCodeAt(i));};
 s(0,'RIFF');v.setUint32(4,36+n*4,true);s(8,'WAVE');s(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,2,true);v.setUint32(24,rate,true);v.setUint32(28,rate*4,true);v.setUint16(32,4,true);v.setUint16(34,16,true);s(36,'data');v.setUint32(40,n*4,true);
 for(let i=0;i<n;i++){const t=i/rate,p=((t-${phase})%(60/${bpm})+60/${bpm})%(60/${bpm});
  const x=Math.sin(t*2*Math.PI*95)*Math.exp(-p/.035)*.55;
  for(let c=0;c<2;c++)v.setInt16(44+i*4+c*2,Math.round(x*32767),true);}
 const a=window.testMedia=new Audio(URL.createObjectURL(new Blob([buffer],{type:'audio/wav'})));a.volume=0;
 window.MusicKit={getInstance:()=>({_targetElement:a})};window.music=MusicKit.getInstance();
 await new Promise(r=>{a.onloadeddata=r;a.load();});(${attachTap.toString()})(a,0);a.volume=1;await a.play();return true;})()`);
 return w;
}
async function info(w){return w.webContents.executeJavaScript('window.__emberFlowAudio.info()');}
function phase(info,grid){return info.wall+(grid.phase-info.outputContext)*1000;}
app.whenReady().then(async()=>{
 try{
  const a=await deck(120,.137),b=await deck(124,.32);await delay(6500);
  const old=await info(a),incoming=await info(b),ga=detectBeat(old.points),gb=detectBeat(incoming.points);
  assert(ga&&gb,'Generated drum grids were not detected');assert(Math.abs(ga.bpm-120)<.6);assert(Math.abs(gb.bpm-124)<.6);
  const request=async(w,r)=>{
   if(r.method==='transport')return w.webContents.executeJavaScript('testMedia.pause();true');
   if(r.method==='seek')return w.webContents.executeJavaScript(`(async()=>{const a=testMedia;a.currentTime=0;await new Promise(r=>{if(!a.seeking)r();else a.addEventListener('seeked',r,{once:true});});window.__emberFlowAudio.points.length=0;return true;})()`);
  };
  const flow=new FlowDecks(a,null,request,''),plan=await flow.align(b,old,incoming,0);
  assert(plan&&Math.abs(plan.rate-120/124)<.005);await delay(4500);
  const oa=await info(a),ib=await info(b),x=detectBeat(oa.points),y=detectBeat(ib.points);assert(x&&y);
  const period=x.period*1000,difference=((phase(ib,y)-phase(oa,x)+period/2)%period+period)%period-period/2;
  assert(Math.abs(difference)<45,'The measured beats did not line up');
  console.log(JSON.stringify({beat_smoke:true,oldBpm:x.bpm,incomingBpm:y.bpm,rate:plan.rate,phaseErrorMs:difference}));
  await flow.restoreRate(b,plan.rate,.5);await delay(650);
  assert(Math.abs((await info(b)).rate-1)<.001,'Normal tempo did not return');
 }catch(e){console.error(e.stack);failed=true;}
 finally{for(const w of windows)if(!w.isDestroyed())w.destroy();app.exit(failed?1:0);}
});
