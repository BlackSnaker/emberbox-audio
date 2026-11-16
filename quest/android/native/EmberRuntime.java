package io.emberbox.quest;

import android.app.*;
import android.content.*;
import android.media.MediaDrm;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;

/** Headset-local, origin-restricted metadata IPC. Never exports service storage. */
public final class EmberRuntime {
    public static final int PORT=8768;
    public static final String ORIGIN="https://blacksnaker.github.io";
    public static final Map<String,String> URLS=new LinkedHashMap<>(),NAMES=new LinkedHashMap<>();
    public static final Set<String> MEDIA_HOSTS=new HashSet<>();
    static {
        URLS.put("apple-music","https://music.apple.com/");NAMES.put("apple-music","Apple Music");
        URLS.put("spotify","https://open.spotify.com/");NAMES.put("spotify","Spotify");
        URLS.put("yandex-music","https://music.yandex.ru/");NAMES.put("yandex-music","Яндекс Музыка");
        URLS.put("youtube","https://www.youtube.com/");NAMES.put("youtube","YouTube");
        for(String url:URLS.values())MEDIA_HOSTS.add(Uri.parse(url).getHost());
    }
    private static EmberRuntime instance;
    public static synchronized EmberRuntime ensure(Context context) {
        if(instance==null) {
            instance=new EmberRuntime(context.getApplicationContext());
            context.startForegroundService(new Intent(context,PlaybackService.class));
        }
        return instance;
    }
    private final Context app;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final Map<String,WebView> views=new HashMap<>();
    private final Map<String,String> scripts=new HashMap<>();
    private final ExecutorService work=new ThreadPoolExecutor(4,4,0,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(64),new ThreadPoolExecutor.CallerRunsPolicy());
    private volatile JSONObject status=new JSONObject(),metrics=new JSONObject();
    private volatile String source;
    private final JSONArray queue=new JSONArray();
    public final String token;
    private volatile float volume=.65f;
    private volatile boolean muted=false;
    private ServerSocket server;
    private volatile boolean closed=false;
    private EmberRuntime(Context context) {
        app=context;
        SharedPreferences prefs=app.getSharedPreferences("ember-private",Context.MODE_PRIVATE);
        String secret=prefs.getString("pair",null);
        if(secret==null){byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);secret=android.util.Base64.encodeToString(bytes,android.util.Base64.URL_SAFE|android.util.Base64.NO_WRAP|android.util.Base64.NO_PADDING);prefs.edit().putString("pair",secret).apply();}
        token=secret;source=prefs.getString("source","apple-music");
        if(!URLS.containsKey(source))source="apple-music";
        try {
            server=new ServerSocket();server.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"),PORT));
            Thread t=new Thread(()->{while(!closed)try{Socket socket=server.accept();work.execute(()->serve(socket));}catch(IOException ignored){break;}},"ember-local-api");t.setDaemon(true);t.start();
        }catch(IOException error){android.util.Log.e("EmberQuest","LOCAL_BRIDGE_UNAVAILABLE");}
        Thread poll=new Thread(()->{while(!closed){
            String selected=source;
            try {JSONObject next=call(selected,"status",new JSONObject());if(selected.equals(source)){status=next;PlaybackService.refresh(next);}}
            catch(Exception ignored){}
            try{Thread.sleep(800);}catch(InterruptedException ignored){break;}
        }},"ember-service-status");poll.setDaemon(true);poll.start();
        android.util.Log.i("EmberQuest","WIDEVINE_SUPPORTED="+MediaDrm.isCryptoSchemeSupported(UUID.fromString("edef8ba9-79d6-4ace-a3c8-27dcd51d21ed")));
    }
    public void transport(String action){work.execute(()->{try{call(source,"transport",new JSONObject().put("action",action));}catch(Exception ignored){}});}
    public static synchronized void shutdown(){if(instance==null)return;EmberRuntime owner=instance;instance=null;owner.closed=true;try{if(owner.server!=null)owner.server.close();}catch(IOException ignored){}owner.ui.post(()->{for(WebView web:owner.views.values())web.destroy();owner.views.clear();});owner.work.shutdownNow();}
    public String roomUrl(){return ORIGIN+"/?app=native#bridge=quest&pair="+token;}
    public void select(String value){
        if(!URLS.containsKey(value))return;
        String previous=source;
        if(!previous.equals(value)){work.execute(()->{try{call(previous,"transport",new JSONObject().put("action","pause"));}catch(Exception ignored){}});status=new JSONObject();}
        source=value;app.getSharedPreferences("ember-private",Context.MODE_PRIVATE).edit().putString("source",value).apply();
    }
    public WebView view(Activity owner,String value){
        WebView existing=views.get(value);if(existing!=null)return existing;
        WebView web=new WebView(owner);
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(true);
        settings.setUseWideViewPort(true);settings.setLoadWithOverviewMode(true);settings.setSupportZoom(true);
        android.webkit.CookieManager.getInstance().setAcceptCookie(true);android.webkit.CookieManager.getInstance().setAcceptThirdPartyCookies(web,true);
        web.setBackgroundColor(android.graphics.Color.rgb(19,25,29));
        web.setWebViewClient(new WebViewClient(){
            @Override public void onPageFinished(WebView view,String url){
                if(isMediaOrigin(value,url))view.evaluateJavascript(adapter(value),null);
                android.webkit.CookieManager.getInstance().flush();
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                String scheme=request.getUrl().getScheme();return !("https".equals(scheme)||"about".equals(scheme));
            }
        });
        views.put(value,web);web.loadUrl(URLS.get(value));return web;
    }
    private boolean isMediaOrigin(String service,String url){
        if(url==null)return false;Uri u=Uri.parse(url);return "https".equals(u.getScheme())&&Uri.parse(URLS.get(service)).getHost().equals(u.getHost());
    }
    private String adapter(String service){
        if(scripts.containsKey(service))return scripts.get(service);
        String file=service.equals("apple-music")?"apple.js":service.equals("spotify")?"spotify.js":service.equals("yandex-music")?"yandex.js":"youtube.js";
        try(InputStream input=app.getAssets().open(file)){
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;
            while((n=input.read(buffer))!=-1)bytes.write(buffer,0,n);
            String script=new String(bytes.toByteArray(),StandardCharsets.UTF_8);scripts.put(service,script);return script;
        }catch(IOException ignored){return "";}
    }
    private String function(String service){return service.equals("apple-music")?"emberboxAppleCommand":service.equals("spotify")?"emberboxSpotifyCommand":service.equals("yandex-music")?"emberboxYandexCommand":"emberboxYoutubeCommand";}
    public JSONObject call(String service,String method,JSONObject params)throws Exception {
        if(!URLS.containsKey(service))throw new IOException("Unsupported source");
        CompletableFuture<JSONObject> result=new CompletableFuture<>();
        String key="__emberQuestResult"+UUID.randomUUID().toString().replace("-","");
        JSONObject request=new JSONObject().put("method",method).put("params",params);
        ui.post(()->{
            WebView web=views.get(service);
            if(web==null||!isMediaOrigin(service,web.getUrl())){result.completeExceptionally(new IOException("Sign in first"));return;}
            String invoke="(async()=>{try{window['"+key+"']=JSON.stringify({data:await "+function(service)+"("+request+")});}catch(e){window['"+key+"']=JSON.stringify({error:'SOURCE_NOT_READY'});}})();";
            web.evaluateJavascript(invoke,null);
            Runnable probe=new Runnable(){int attempts=0;public void run(){
                if(result.isDone())return;
                if(++attempts>240){result.completeExceptionally(new IOException("Source timed out"));return;}
                web.evaluateJavascript("window['"+key+"']||null",encoded->{
                    if(result.isDone())return;
                    try {
                        Object raw=new JSONTokener(encoded==null?"null":encoded).nextValue();
                        if(raw instanceof String){
                            web.evaluateJavascript("delete window['"+key+"']",null);JSONObject response=new JSONObject((String)raw);
                            if(response.has("error"))result.completeExceptionally(new IOException("Source not ready"));
                            else result.complete(response.optJSONObject("data")!=null?response.optJSONObject("data"):new JSONObject());
                        }else ui.postDelayed(this,80);
                    }catch(JSONException error){result.completeExceptionally(new IOException("Invalid source reply"));}
                });
            }};ui.postDelayed(probe,40);
        });
        try{return result.get(22,TimeUnit.SECONDS);}finally{result.cancel(false);}
    }
    public JSONObject state()throws JSONException {
        JSONObject s=new JSONObject(status.toString());s.put("source",source);s.put("native",true);s.put("companion",false);
        if(s.optString("title").isEmpty())s.put("title","Твоя музыка на Quest");
        s.put("album",s.optString("album"));s.put("artist",s.optString("artist",NAMES.get(source)));
        s.put("volume",volume);s.put("muted",muted);s.put("flow",false);s.put("levels",new JSONArray());
        s.put("audio",new JSONObject().put("native",true));s.put("queue",new JSONArray(queue.toString()));
        s.put("artistRef",new JSONObject().put("name",s.optString("artist")).put("songId",s.optString("id")).put("songUri",s.optString("uri")).put("current",true));
        s.put("albumRef",new JSONObject().put("title",s.optString("album")).put("songId",s.optString("id")).put("songUri",s.optString("uri")).put("current",true));
        return s;
    }
    public JSONObject action(JSONObject data)throws Exception {
        String op=data.optString("op");Object value=data.opt("value");JSONObject p=new JSONObject();
        if(op.equals("source")){String next=data.optString("value");if(!URLS.containsKey(next))throw new IOException("Invalid source");select(next);return new JSONObject().put("ok",true).put("needsLogin",true).put("source",next);}
        if(op.equals("login"))return new JSONObject().put("ok",true).put("needsLogin",true).put("source",source);
        if(op.equals("toggle")||op.equals("next")||op.equals("previous"))return call(source,"transport",p.put("action",op));
        if(op.equals("seek"))return call(source,"seek",p.put("position",number(value,0,86400)));
        if(op.equals("play")){JSONObject item=data.getJSONObject("item");return call(source,"play",p.put("id",item.optString("id")).put("kind",item.optString("kind")).put("uri",item.optString("uri")));}
        if(op.equals("volume")||op.equals("mute")){
            if(op.equals("volume"))volume=(float)number(value,0,1);else muted=!muted;
            float level=muted?0:volume;
            ui.post(()->{WebView web=views.get(source);if(web!=null)web.evaluateJavascript("(()=>{for(const m of document.querySelectorAll('audio,video'))m.volume="+level+";const a=window.MusicKit?.getInstance?.();try{if(a)a.volume="+level+";}catch{}})()",null);});
            return new JSONObject().put("ok",true);
        }
        if(op.equals("queue")){JSONArray items=data.optJSONArray("items");if(items!=null)for(int i=0;i<items.length()&&queue.length()<100;i++)queue.put(items.getJSONObject(i));return new JSONObject().put("ok",true);}
        if(op.equals("queue-clear")){while(queue.length()>0)queue.remove(0);return new JSONObject().put("ok",true);}
        if(op.equals("favorite"))return call(source,"favorite",p.put("value",data.optBoolean("value")).put("id",status.optString("id")).put("kind",source.equals("apple-music")?"songs":"track").put("uri",status.optString("uri")));
        throw new UnsupportedOperationException("native-feature-unavailable");
    }
    private double number(Object value,double min,double max)throws IOException {try{double d=Double.parseDouble(String.valueOf(value));if(Double.isFinite(d))return Math.max(min,Math.min(max,d));}catch(Exception ignored){}throw new IOException("Invalid number");}
    private JSONObject browse(JSONObject data)throws Exception {
        String category=data.optString("category","home"),method="browse";JSONObject p=new JSONObject().put("offset",Math.max(0,data.optInt("offset")));
        JSONObject c=data.optJSONObject("collection");
        if(category.equals("search")){method="search";p.put("term",data.optString("term"));}
        else if(category.equals("artist")){method="artist";if(c!=null)p=c;}
        else if(category.equals("artist-section")){method="artistSection";if(c!=null)p=c;}
        else if(category.equals("release")){method="release";if(c!=null)p=c;}
        else if(c!=null){method="tracks";p.put("kind",c.optString("kind")).put("id",c.optString("id")).put("uri",c.optString("uri"));}
        else p.put("category",category.equals("albums")?"albums":category.equals("favorites")?"songs":source.equals("apple-music")?"playlists":"home");
        return call(source,method,p);
    }
    private void serve(Socket socket){
        try{Socket s=socket;s.setSoTimeout(5000);InputStream in=s.getInputStream();String first=line(in);if(first==null)return;String[] start=first.split(" ");if(start.length<2)return;
            Map<String,String> h=new HashMap<>();String field;int headerSize=first.length();
            while((field=line(in))!=null&&!field.isEmpty()){headerSize+=field.length();if(headerSize>16384)throw new IOException();int split=field.indexOf(':');if(split>0)h.put(field.substring(0,split).toLowerCase(Locale.ROOT),field.substring(split+1).trim());}
            String origin=h.get("origin"),host=h.get("host");boolean same=origin==null||ORIGIN.equals(origin);
            if(!same||!("localhost:"+PORT).equals(host)&&!("127.0.0.1:"+PORT).equals(host)){reply(s,403,new JSONObject().put("error","Origin not allowed"),null);return;}
            if(start[0].equals("OPTIONS")){reply(s,204,new JSONObject(),origin);return;}
            if(start[1].equals("/api/capabilities")){reply(s,200,new JSONObject().put("native",true).put("widevine",MediaDrm.isCryptoSchemeSupported(UUID.fromString("edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"))),origin);return;}
            if(!MessageDigest.isEqual(("Bearer "+token).getBytes(StandardCharsets.UTF_8),h.getOrDefault("authorization","").getBytes(StandardCharsets.UTF_8))){reply(s,403,new JSONObject().put("error","Pair this app first"),origin);return;}
            if(start[0].equals("GET")&&start[1].equals("/api/state")){reply(s,200,state(),origin);return;}
            if(start[0].equals("GET")&&start[1].equals("/api/metrics")){reply(s,200,metrics,origin);return;}
            if(start[0].equals("GET")&&start[1].startsWith("/api/image?")){image(s,start[1],origin);return;}
            if(!start[0].equals("POST")){reply(s,404,new JSONObject().put("error","Endpoint unavailable"),origin);return;}
            int size=Integer.parseInt(h.getOrDefault("content-length","0"));if(size<2||size>128000)throw new IOException();byte[] body=new byte[size];int offset=0,n;while(offset<size&&(n=in.read(body,offset,size-offset))>0)offset+=n;if(offset!=size)throw new IOException();
            JSONObject data=new JSONObject(new String(body,StandardCharsets.UTF_8)),response;
            if(start[1].equals("/api/action"))response=action(data);
            else if(start[1].equals("/api/browse"))response=browse(data);
            else if(start[1].equals("/api/metrics")){metrics=data;response=new JSONObject().put("ok",true);}
            else{reply(s,404,new JSONObject().put("error","Endpoint unavailable"),origin);return;}
            reply(s,200,response,origin);
        }catch(Exception ignored){try{reply(socket,ignored instanceof UnsupportedOperationException?400:502,new JSONObject().put("error",ignored instanceof UnsupportedOperationException?"Эта функция ещё не перенесена в нативный движок Quest.":"Открой вход в музыкальный сервис на Quest и дождись загрузки."),ORIGIN);}catch(Exception ignoredAgain){}}finally{try{socket.close();}catch(IOException ignored){}}
    }
    private String line(InputStream in)throws IOException {ByteArrayOutputStream out=new ByteArrayOutputStream();int c;while((c=in.read())!=-1){if(c=='\n')break;if(c!='\r')out.write(c);if(out.size()>8192)throw new IOException();}return c==-1&&out.size()==0?null:out.toString("UTF-8");}
    private void reply(Socket s,int status,JSONObject value,String origin)throws IOException {byte[] body=value.toString().getBytes(StandardCharsets.UTF_8);send(s,status,"application/json",body,origin);}
    private void send(Socket socket,int status,String mime,byte[] body,String origin)throws IOException {
        if(status==204)body=new byte[0];
        String headers="HTTP/1.1 "+status+" OK\r\nContent-Type: "+mime+"\r\nContent-Length: "+body.length+"\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n";
        if(ORIGIN.equals(origin))headers+="Access-Control-Allow-Origin: "+ORIGIN+"\r\nVary: Origin\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Authorization, Content-Type\r\nAccess-Control-Allow-Private-Network: true\r\n";
        OutputStream out=socket.getOutputStream();out.write((headers+"\r\n").getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();
    }
    private void image(Socket socket,String path,String origin)throws Exception {
        Uri query=Uri.parse("http://localhost"+path);String raw=query.getQueryParameter("url");URL url=new URL(raw==null?"":raw);String host=url.getHost();
        boolean allowed=false;for(String suffix:new String[]{"mzstatic.com","scdn.co","ytimg.com","yandex.net","yandex.ru"})if(host.equals(suffix)||host.endsWith("."+suffix))allowed=true;
        if(!url.getProtocol().equals("https")||!allowed)throw new IOException();
        HttpURLConnection connection=(HttpURLConnection)url.openConnection();connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(8000);connection.setReadTimeout(8000);
        try{if(connection.getResponseCode()!=200)throw new IOException();String type=connection.getContentType();if(type==null||!type.matches("image/(jpeg|png|webp).*"))throw new IOException();
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=connection.getInputStream()){byte[] block=new byte[8192];int n;while((n=in.read(block))!=-1){bytes.write(block,0,n);if(bytes.size()>4000000)throw new IOException();}}
            send(socket,200,type.split(";")[0],bytes.toByteArray(),origin);
        }finally{connection.disconnect();}
    }
}
