/* Private native-audio source adapter. Signed URLs and account tokens stay here. */
async function emberboxSpatialSource(params) {
 'use strict';
 if(location.origin!=='https://music.apple.com')throw Error('SIGN_IN_REQUIRED');
 const music=window.MusicKit?.getInstance?.();
 if(!music?.isAuthorized)throw Error('SIGN_IN_REQUIRED');
 const attr=line=>Object.fromEntries([...line.matchAll(/(?:^|,)([A-Z0-9-]+)=("[^"]*"|[^,]*)/g)].map(m=>[m[1],m[2].replace(/^"|"$/g,'')]));
 const decode=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 const encode=value=>{let s='';for(let i=0;i<value.length;i+=16384)s+=String.fromCharCode(...value.subarray(i,i+16384));return btoa(s);};
 const canonical=uri=>{const raw=uri.includes('base64,')?decode(uri.split('base64,')[1]):new TextEncoder().encode(uri);return raw.length===16?'data:;base64,'+encode(raw):uri;};
 const widevine=a=>a.KEYFORMAT==='com.widevine'||a.KEYFORMAT==='urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed';
 const contexts=window.__emberSpatialContexts||(window.__emberSpatialContexts=new Map());
 const safeUrl=value=>{const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password||!['apple.com','applemusic.com','cdn-apple.com','mzstatic.com'].some(h=>u.hostname===h||u.hostname.endsWith('.'+h)))throw Error('SPATIAL_SOURCE_UNSUPPORTED');return u;};
 async function bytes(value,max=524288,range){
  const u=safeUrl(value),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),7000);
  try {
   const response=await fetch(u,{signal:controller.signal,credentials:'omit',headers:range?{Range:'bytes='+range.start+'-'+(range.start+range.length-1)}:{}});
   if(!response.ok||range&&response.status!==206)throw Error('SPATIAL_NETWORK');
   const reader=response.body.getReader(),parts=[];let size=0;
   try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>max)throw Error('SPATIAL_SOURCE_LIMIT');parts.push(value);}}
   finally{await reader.cancel();}
   const data=new Uint8Array(size);let offset=0;for(const part of parts){data.set(part,offset);offset+=part.length;}return data;
  }finally{clearTimeout(timer);}
 }
 function range(value,fallback=0){
  const m=/^(\d+)(?:@(\d+))?$/.exec(value||'');if(!m)throw Error('SPATIAL_SOURCE_UNSUPPORTED');
  const length=Number(m[1]),start=m[2]?Number(m[2]):fallback;
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(length)||!Number.isSafeInteger(start+length)||length<1||length>4194304)throw Error('SPATIAL_SOURCE_LIMIT');
  return {start,length};
 }
 if(params.action==='prepare'||params.action==='inspect') {
  if(params.action==='prepare'&&contexts.size>=2)throw Error('SPATIAL_BUSY');
  let current=music.nowPlayingItem;
  if(params.id!==undefined){
   if(!['songs','library-songs'].includes(params.kind)||!/^\w[\w.-]{0,199}$/.test(String(params.id)))throw Error('INVALID_ARGUMENTS');
   const sf=String(music.storefrontId||music.storefrontCountryCode||'us').toLowerCase();
   if(!/^[a-z]{2}$/.test(sf))throw Error('SPATIAL_SOURCE_UNSUPPORTED');
   const endpoint=params.kind==='library-songs'?'/v1/me/library/songs/'+encodeURIComponent(params.id)+'/catalog':'/v1/catalog/'+sf+'/songs/'+params.id;
   const response=await music.api.music(endpoint,{extend:'audioVariants,extendedAssetUrls'}),resource=(response?.data?.data||response?.data||[])[0];
   if(!resource?.attributes?.playParams)throw Error('SPATIAL_SOURCE_UNSUPPORTED');
   const a=resource.attributes,clone=Object.create(current||null);
   for(const [key,value] of Object.entries({id:resource.id,catalogId:resource.id,type:'song',attributes:a,playParams:a.playParams,isLibrary:false,isLibraryItem:false,isSong:true,isMusicVideo:false}))Object.defineProperty(clone,key,{value});
   current=clone;
  }
  const subscription=await music._playbackController?.services?.store?.storekit?.hasMusicSubscription?.();
  if(subscription!==true)throw Error('SUBSCRIPTION_REQUIRED');
  const asset=await music.services.assetResolver.resolveCatalogSongAsset(current,{hlsEnhancedAsset:params.enhanced!==false,subscription,...(['CBC','CTR'].includes(params.encryption)?{hlsEncryption:params.encryption}:{})});
  if(params.action==='inspect'&&params.extended===true){
   const url=current.attributes?.extendedAssetUrls?.enhancedHls;
   if(typeof url!=='string')throw Error('SPATIAL_NO_ATMOS_ASSET');asset.assetURL=safeUrl(url).href;
  }
  const lines=new TextDecoder().decode(await bytes(asset.assetURL)).split(/\r?\n/).map(s=>s.trim()),variants=[],offered=[];
  for(let i=0;i<lines.length;i++)if(lines[i].startsWith('#EXT-X-STREAM-INF:')){
   const a=attr(lines[i].slice(18));
   offered.push({codecs:String(a.CODECS||'').split(',').filter(v=>['ec-3','ac-3','alac','flac','mp4a.40.2','mp4a.40.5','mp4a.40.29'].includes(v)),bandwidth:Number(a.BANDWIDTH)||0,sampleRate:Number(a['SAMPLE-RATE'])||0});
   if(((a.CODECS||'').split(',').includes('ec-3')||params.allowStereo===true&&(a.CODECS||'').includes('mp4a.40.2'))&&lines[i+1]&&!lines[i+1].startsWith('#'))variants.push({a,uri:lines[i+1]});
  }
  if(params.action==='inspect'){
   const protection=[];
   if(params.extended===true){
    for(let i=0;i<lines.length;i++)if(lines[i].startsWith('#EXT-X-STREAM-INF:')){
     const a=attr(lines[i].slice(18)),codecs=String(a.CODECS||'').split(',');
     if(codecs.some(v=>['alac','flac'].includes(v))&&lines[i+1]&&!lines[i+1].startsWith('#')&&protection.length<4){
      const list=new TextDecoder().decode(await bytes(new URL(lines[i+1],asset.assetURL).href));
      const keys=list.split(/\r?\n/).filter(s=>s.startsWith('#EXT-X-KEY:')).map(s=>attr(s.slice(11)));
      protection.push({codecs:codecs.filter(v=>['alac','flac'].includes(v)),widevine:keys.some(widevine),fairplay:keys.some(a=>a.KEYFORMAT==='com.apple.streamingkeydelivery'),
       methods:[...new Set(keys.map(a=>a.METHOD).filter(v=>['SAMPLE-AES','SAMPLE-AES-CTR','NONE','AES-128'].includes(v)))],
       widevineInitBytes:keys.filter(widevine).slice(0,16).map(a=>a.URI?.includes('base64,')?decode(a.URI.split('base64,')[1]).length:0)});
     }
    }
   }
   return {enhanced:params.enhanced!==false,extended:params.extended===true,variants:offered.slice(0,128),protection};
  }
  if(!variants.length)throw Error('SPATIAL_NO_ATMOS_ASSET');
  const selected=variants.sort((a,b)=>Number(b.a.CODECS.includes('ec-3'))-Number(a.a.CODECS.includes('ec-3'))||Number(b.a.BANDWIDTH)-Number(a.a.BANDWIDTH))[0];
  let leaf=new URL(selected.uri,asset.assetURL).href;
  const audio=lines.filter(s=>s.startsWith('#EXT-X-MEDIA:')).map(s=>attr(s.slice(13))).find(a=>a.TYPE==='AUDIO'&&a['GROUP-ID']===selected.a.AUDIO&&a.URI&&/JOC/.test(a.CHANNELS||''));
  if(audio)leaf=new URL(audio.URI,asset.assetURL).href;
  const media=new TextDecoder().decode(await bytes(leaf)).split(/\r?\n/).map(s=>s.trim());
  const licences=[],segments=[];let map=null,slice=null,end=0,previous='',duration=0,start=0,keyIndex=-1;
  for(const line of media){
   if(line.startsWith('#EXT-X-KEY:')){
    const a=attr(line.slice(11));if(!widevine(a))continue;
    const keyuri=canonical(a.URI);keyIndex=licences.findIndex(v=>v.keyuri===keyuri);
    if(keyIndex<0){
     const raw=a.URI.includes('base64,')?decode(a.URI.split('base64,')[1]):new TextEncoder().encode(a.URI);let pssh=raw;
     if(raw.length===16){pssh=new Uint8Array(52);pssh.set([0,0,0,52,112,115,115,104,0,0,0,0,237,239,139,169,121,214,74,206,163,200,39,220,213,29,33,237,0,0,0,20,8,1,18,16]);pssh.set(raw,36);}
     if(pssh.length>131072||licences.length>=16)throw Error('SPATIAL_SOURCE_LIMIT');
     keyIndex=licences.length;licences.push({keyuri,pssh:encode(pssh)});
    }
   } else if(line.startsWith('#EXT-X-MAP:')){const a=attr(line.slice(11));map={url:new URL(a.URI,leaf).href,range:a.BYTERANGE?range(a.BYTERANGE):null};}
   else if(line.startsWith('#EXT-X-BYTERANGE:'))slice=line.slice(17);
   else if(line.startsWith('#EXTINF:'))duration=Number(line.slice(8).split(',')[0]);
   else if(line&&!line.startsWith('#')){
    if(!map||keyIndex<0||!Number.isFinite(duration)||duration<=0||duration>30||segments.length>=4096)throw Error('SPATIAL_SOURCE_UNSUPPORTED');
    const url=new URL(line,leaf).href,part=slice?range(slice,url===previous?end:0):null;
    segments.push({url,range:part,map,keyIndex,start,duration});start+=duration;previous=url;end=part?part.start+part.length:0;slice=null;duration=0;
   }
  }
  if(!segments.length)throw Error('SPATIAL_SOURCE_UNSUPPORTED');
  const certificate=await bytes(asset.keyCertURL,131072),item=Object.create(current),contextId=crypto.randomUUID();
  Object.defineProperty(item,'keyURLs',{value:{'hls-key-server-url':asset.keyServerURL,'widevine-cert-url':asset.keyCertURL}});
  contexts.set(contextId,{item,asset,licences,segments,cache:null});
  const a=current.attributes||{},art=a.artwork?.url||'';
  const names={'atmos':'dolby-atmos','surround':'dolby-audio','hiResLossless':'hi-res-lossless'};
  const formats=[...new Set([...(Array.isArray(a.audioVariants)?a.audioVariants:[]),...(Array.isArray(a.audioTraits)?a.audioTraits:[])].map(v=>names[v]||v).filter(v=>['dolby-atmos','dolby-audio','hi-res-lossless','lossless','lossy-stereo'].includes(v)))];
  const metadata={id:String(params.id||current.id),catalogId:String(current.catalogId||current.id),title:String(a.name||''),artist:String(a.artistName||''),album:String(a.albumName||''),duration:Number(a.durationInMillis||0)/1000,image:art.replace('{w}','1200').replace('{h}','1200'),availableFormats:formats.length?formats:selected.a.CODECS.includes('ec-3')?['dolby-atmos']:['lossy-stereo'],authorized:true,ready:true};
  return {metadata,codec:selected.a.CODECS.includes('ec-3')?'eac3':'aac',contextId,certificate:encode(certificate),licences:licences.map(v=>({pssh:v.pssh})),segments:segments.map(({start,duration,keyIndex})=>({start,duration,keyIndex}))};
 }
 const ctx=contexts.get(params.contextId);if(!ctx)throw Error('SPATIAL_STALE_CONTEXT');
 if(params.action==='license'){
  const index=Number(params.index),licence=ctx.licences[index];
  if(!Number.isInteger(index)||!licence||typeof params.challenge!=='string'||params.challenge.length>174764)throw Error('INVALID_ARGUMENTS');
  const response=await music.services.license.requestLicense(ctx.item,{keyuri:licence.keyuri,licenseChallenge:decode(params.challenge)},{userInitiated:true});
  if(response.status!==0||typeof response.license!=='string'){
   const error=Error(response.status===-1004?'DEVICE_LIMIT':'SPATIAL_LICENSE_REJECTED');
   if(Number.isInteger(response.status))error.appleStatus=response.status;throw error;
  }
  licence.response=response;return {license:response.license};
 }
 if(params.action==='segment'){
  const index=Number(params.index),offset=Number(params.offset||0),segment=ctx.segments[index];
  if(!Number.isInteger(index)||!segment||!Number.isSafeInteger(offset)||offset<0||offset>8388608)throw Error('INVALID_ARGUMENTS');
  if(ctx.cache?.index!==index){
   const init=await bytes(segment.map.url,1048576,segment.map.range),body=await bytes(segment.url,4194304,segment.range);
   const data=new Uint8Array(init.length+body.length);data.set(init);data.set(body,init.length);ctx.cache={index,data,bodyKind:new TextDecoder().decode(body.subarray(4,8)).replace(/[^a-z0-9 ]/gi,'?'),initBytes:init.length,originalOffset:new URL(segment.map.url).origin+new URL(segment.map.url).pathname===new URL(segment.url).origin+new URL(segment.url).pathname?(segment.range?.start||0):0};
  }
  const data=ctx.cache.data;if(offset>=data.length)throw Error('INVALID_ARGUMENTS');
  return {data:encode(data.subarray(offset,offset+393216)),total:data.length,initBytes:ctx.cache.initBytes,originalOffset:ctx.cache.originalOffset,bodyKind:ctx.cache.bodyKind};
 }
 if(params.action==='close'){
  contexts.delete(params.contextId);ctx.cache=null;
  for(const licence of ctx.licences)if(licence.response)await music.services.license.revokeLicense(ctx.item,{keyuri:licence.keyuri},{userInitiated:false,stkn:licence.response.stkn}).catch(()=>{});
  return {closed:true};
 }
 throw Error('UNSUPPORTED');
}
