/* Actual CDP Media event shapes, with no account/network fixtures. */
const assert=require('node:assert/strict');
const {MediaQuality,audioConfig}=require('../src/apple_web_host/media_quality.cjs');
const tracker=new MediaQuality();
function config(id,codec='aac',rate=44100) {
  tracker.message('Media.playerPropertiesChanged',{playerId:id,properties:[
    {name:'kAudioTracks',value:JSON.stringify([{codec,'samples per second':rate,channels:2,'bytes per channel':4,'sample format':'Float 32','private':'NEVER_EXPORT'}])},
    {name:'url',value:'https://private.invalid/?token=NEVER_EXPORT'}]});
}
function event(id,event){tracker.message('Media.playerEventsAdded',{playerId:id,events:[{value:JSON.stringify({event})}]});}
config('playing');event('playing','kPlay');
let quality=tracker.snapshot('first');
assert.equal(quality.codec,'aac');assert.equal(quality.sampleRate,44100);assert.equal(quality.bitDepth,undefined);
assert(!JSON.stringify(quality).includes('NEVER_EXPORT'));
config('prefetch','flac',96000);
assert.equal(tracker.snapshot('first').codec,'aac','Preloading must not claim Lossless');
tracker.message('Media.playerPropertiesChanged',{playerId:'artwork',properties:[{name:'kAudioTracks',value:'[]'}]});
event('artwork','kPlay');assert.equal(tracker.snapshot('first').codec,'aac','Silent animated artwork must not steal audio quality');
assert.deepEqual(tracker.snapshot('second'),{},'New song must not retain old quality');
event('prefetch','kPlay');assert.deepEqual(tracker.snapshot('second'),{},'Overlapping audio streams are ambiguous');
event('playing','kPause');assert.equal(tracker.snapshot('second').codec,'flac');
event('prefetch','kPause');assert.equal(tracker.snapshot('second').codec,'flac','Pause retains the current format');
event('prefetch','kLoad');assert.deepEqual(tracker.snapshot('second'),{});
config('prefetch','opus',48000);event('prefetch','kPlay');assert.equal(tracker.snapshot('second').codec,'opus');
event('prefetch','kWebMediaPlayerDestroyed');assert.deepEqual(tracker.snapshot('second'),{});
assert.deepEqual(audioConfig({codec:'secret',url:'NEVER_EXPORT'}),{});
tracker.message('Media.playerPropertiesChanged',{playerId:'bad',properties:[{name:'kAudioTracks',value:'invalid json'}]});
for(let i=0;i<40;i++)config('bounded'+i);
assert(tracker.players.size<=32);tracker.reset();assert.deepEqual(tracker.snapshot('new'),{});
console.log('PASS decoder format, prefetch isolation, track transitions, bounded state and private-field filtering');
