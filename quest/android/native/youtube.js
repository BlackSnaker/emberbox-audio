async function emberboxYoutubeCommand(request){
 if(location.origin!=='https://www.youtube.com')throw Error('NOT_READY');
 const p=request.params||{},player=document.querySelector('video'),data=document.querySelector('#movie_player')?.getVideoData?.()||{};
 if(request.method==='status')return {ready:true,authorized:true,title:data.title||navigator.mediaSession?.metadata?.title||'',artist:data.author||'',album:'YouTube',id:data.video_id||'',image:data.video_id?'https://i.ytimg.com/vi/'+data.video_id+'/hqdefault.jpg':'',position:player?.currentTime||0,duration:Number.isFinite(player?.duration)?player.duration:0,playing:!!player&&!player.paused};
 if(request.method==='transport'){if(!player)throw Error('NOT_READY');if(p.action==='pause')player.pause();else if(p.action==='resume')await player.play();else if(p.action==='toggle'){if(player.paused)await player.play();else player.pause();}else document.querySelector(p.action==='previous'?'.ytp-prev-button':'.ytp-next-button')?.click();return {ok:true};}
 if(request.method==='seek'){if(player)player.currentTime=Number(p.position)||0;return {ok:true};}
 if(request.method==='play'){const id=String(p.id||'').replace(/^youtube:/,'');if(!/^[A-Za-z0-9_-]{11}$/.test(id))throw Error('INVALID_ID');location.href='/watch?v='+id;return {ok:true};}
 const items=Array.from(document.querySelectorAll('a#video-title,a#video-title-link')).map(a=>{const id=new URL(a.href,location.href).searchParams.get('v');return {id,uri:'youtube:'+id,title:a.textContent.trim(),artist:'YouTube',kind:'track',image:'https://i.ytimg.com/vi/'+id+'/hqdefault.jpg'};}).filter(v=>v.id&&v.title).slice(0,40);
 if(request.method==='browse')return {items};
 throw Error('NOT_READY');
}
