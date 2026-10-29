'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Scenes,signature}=require('../src/apple_web_host/scene.cjs');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ember-scenes-')),file=path.join(root,'config.json');
try{
 fs.writeFileSync(file,JSON.stringify({enabled:true}));const s=new Scenes(file);
 assert.equal(s.enabled,true);assert.equal(s.render().mode,'headphones');
 const bt={key:'a'.repeat(32),kind:'headphones',label:'Bluetooth pair',bluetooth:true,codec:'sbc',rate:48000};
 s.setOutput(bt);s.set({mode:'speakers',angle:30});
 assert.equal(s.render().mode,'speakers','Misreported Bluetooth form factor must permit a saved speaker override');
 s.save(false);const restored=new Scenes(file);assert.equal(restored.enabled,false);
 restored.setOutput(bt);assert.equal(restored.render().mode,'speakers','Toggling native audio lost the device scene');
 restored.setOutput({...bt,key:'b'.repeat(32),label:'Other headphones'});assert.equal(restored.render().mode,'headphones');
 restored.set({mode:'headphones',hrtf:1});assert.notEqual(signature(restored.render()),signature(s.render()));
 restored.setOutput(bt);assert.equal(restored.render().angle,30);restored.set({mode:'auto'});assert.equal(restored.render().mode,'headphones');
 assert.throws(()=>s.set({mode:'speakers',angle:180}),/INVALID_ARGUMENTS/);
 assert.throws(()=>s.set({mode:'headphones',hrtf:9}),/INVALID_ARGUMENTS/);
 assert.throws(()=>s.setOutput({...bt,label:'bad\nlabel'}),/INVALID_ARGUMENTS/);
 assert(!fs.readFileSync(file,'utf8').includes('Bluetooth pair'),'Device names must not be persisted');
 const early=new Scenes();early.set({mode:'speakers'});early.setOutput(bt);
 assert.equal(early.render().mode,'speakers');early.setOutput({...bt,key:'c'.repeat(32)});assert.equal(early.render().mode,'headphones');
 console.log('PASS scene migration, physical override, per-device memory, automatic selection and validation');
}finally{fs.rmSync(root,{recursive:true,force:true});}
