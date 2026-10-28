/* Typed official-site controls; credentials and full player state stay in-page. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const calls=[];
let paused=false,signed=true,media=null;
const state={isPaused:false,positionAsOfTimestamp:34000,item:{uri:'spotify:track:TRACK123',metadata:{title:'Original fixture',artist_name:'Fixture artist',album_title:'Fixture album',album_uri:'spotify:album:ALBUM123',duration:'240000',accessToken:'PRIVATE-SENTINEL'}},token:'PRIVATE-SENTINEL'};
const player={getState:()=>({...state,isPaused:paused}),play:async(...args)=>calls.push(['play',...args]),pause:async()=>{paused=true;calls.push(['pause']);},resume:async()=>calls.push(['resume']),skipToNext:async()=>calls.push(['next']),seekTo:async n=>calls.push(['seek',n])};
const provider={getRegistry:()=>({_map:new Map([[Symbol('PlayerAPI'),true]]),resolve:()=>player})};
// The registry key is matched by its public symbol description, not identity.
const main={__reactFiberFixture:{memoizedProps:{value:provider}},querySelector:()=>null,querySelectorAll:()=>[]};
const doc={readyState:'complete',querySelector:q=>q==='main'?main:q==='audio,video'?media:q.includes('user-widget')?(signed?{}:null):q.includes('control-button')?{disabled:false,click(){calls.push(['button']);}}:null,querySelectorAll:()=>[]};
const context=vm.createContext({document:doc,location:{origin:'https://open.spotify.com',pathname:'/'},navigator:{mediaSession:{}},window:{__emberboxPlaybackAllowed:true},URL,Map,Set,Date,console,setTimeout,getComputedStyle:node=>({fontSize:String(node.size||0),backgroundImage:node.background||'none'})});
vm.runInContext(fs.readFileSync('src/apple_web_host/spotify.js','utf8')+'\nglobalThis.command=emberboxSpotifyCommand;',context);
(async()=>{
 let s=await context.command({method:'status'});assert.equal(s.authorized,true);assert.equal(s.id,'TRACK123');assert.equal(s.duration,240);assert.equal(s.position,34);assert.equal(s.albumId,'ALBUM123');assert.equal(s.capabilities.player,true);assert(!JSON.stringify(s).includes('PRIVATE-SENTINEL'));assert.equal(s.emberFlow,false);
 // Some web playback snapshots omit album_uri; keep only the catalogue's
 // named album reference so the album label still opens the exact recording.
 const albumUri=state.item.metadata.album_uri;delete state.item.metadata.album_uri;
 context.window.__emberboxSpotifyMusic=new Map([['TRACK123',{albumId:'CATALOGUE_ALBUM'}]]);
 assert.equal((await context.command({method:'status'})).albumId,'CATALOGUE_ALBUM');
 state.item.metadata.album_uri=albumUri;
 await context.command({method:'play',params:{uri:'spotify:track:TRACK123'}});assert.equal(calls.at(-1)[1].uri,'spotify:track:TRACK123');
 await context.command({method:'seek',params:{position:23}});assert.deepEqual(calls.at(-1),['seek',23000]);
 await context.command({method:'transport',params:{action:'next'}});assert.deepEqual(calls.at(-1),['next']);
 state.timestamp=Date.now()-4000;s=await context.command({method:'status'});assert(s.position>=38&&s.position<40);delete state.timestamp;
 // A service-denied seek must never fall through to a media-element workaround.
 media={duration:240,currentTime:0,paused:false};const seek=player.seekTo;
 player.seekTo=async()=>{throw Error('Action is currently disallowed');};
 await assert.rejects(context.command({method:'seek',params:{position:42}}),/PLAYBACK_RESTRICTED/);assert.equal(media.currentTime,0);player.seekTo=seek;media=null;

 const count=calls.length;context.window.__emberboxPlaybackAllowed=false;
 await context.command({method:'play',params:{uri:'spotify:track:TRACK123'}});await context.command({method:'transport',params:{action:'next'}});assert.equal(calls.length,count);
 await context.command({method:'transport',params:{action:'pause'}});assert.deepEqual(calls.at(-1),['pause']);
 context.window.__emberboxPlaybackAllowed=true;
 for(const uri of ['spotify:track:abc;alert(1)','https://evil.invalid/track/123','spotify:user:PRIVATE-SENTINEL'])await assert.rejects(context.command({method:'play',params:{uri}}),/INVALID_ARGUMENTS/);
 await assert.rejects(context.command({method:'seek',params:{position:-1}}),/INVALID_ARGUMENTS/);
 await assert.rejects(context.command({method:'evaluate',params:{expression:'document.cookie'}}),/INVALID_ARGUMENTS/);

 // New web artist headers are display spans. A sidebar h1 is not the artist.
 context.location.pathname='/artist/ARTIST123';
 const decoration={background:'url("https://open.spotifycdn.com/cdn/images/loading-strip.png")'};
 const display={textContent:'Fixture artist',size:80},header={querySelectorAll:q=>q==='span,div,h1,h2,p'?[display]:[]};
 const card={querySelector:q=>q.includes('cardTitle')?{textContent:'Fixture release'}:null};
 const album={getAttribute:()=>'/album/ALBUM123',closest:()=>card,textContent:'Fixture release'};
 main.querySelector=q=>q==='[data-testid="entity-header"]'?header:null;
 main.querySelectorAll=q=>q==='a[href*="/album/"]'?[album]:q==='a[href]'?[album]:q==='div'?[decoration]:[];
 const a=await context.command({method:'artist',params:{id:'ARTIST123'}});assert.equal(a.artist.name,'Fixture artist');assert.equal(a.sections[0].items.length,1);assert.equal(a.artist.image,'','Page decorations are not artist portraits');
 context.location.pathname='/';
 signed=false;await assert.rejects(context.command({method:'browse',params:{category:'home'}}),/SIGN_IN_REQUIRED/);
 context.location.origin='https://accounts.spotify.com';await assert.rejects(context.command({method:'status'}),/NOT_READY/);
 console.log('PASS Spotify site status, URI playback, account isolation, transport, seek, source pause and private-field filtering');
})().catch(e=>{console.error(e);process.exitCode=1;});
