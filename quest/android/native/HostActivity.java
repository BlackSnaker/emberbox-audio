package io.emberbox.quest;

import android.app.*;
import android.os.*;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.view.*;
import android.webkit.*;
import android.widget.*;

/** Official provider pages only. Credentials remain inside their WebView. */
public class HostActivity extends Activity {
    private LinearLayout frame;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        EmberRuntime runtime=EmberRuntime.ensure(this);
        String source=getIntent().getStringExtra("source");
        if(source==null&&getIntent().getData()!=null)source=getIntent().getData().getLastPathSegment();
        if(!EmberRuntime.URLS.containsKey(source))source="apple-music";
        runtime.select(source);
        frame=new LinearLayout(this);frame.setOrientation(LinearLayout.VERTICAL);frame.setBackgroundColor(Color.rgb(19,25,29));
        LinearLayout bar=new LinearLayout(this);bar.setGravity(Gravity.CENTER_VERTICAL);bar.setPadding(20,10,20,10);
        TextView title=new TextView(this);title.setText("EMBER  ·  "+EmberRuntime.NAMES.get(source));title.setTextColor(Color.rgb(242,225,185));title.setTextSize(18);bar.addView(title,new LinearLayout.LayoutParams(0,56,1));
        Button back=new Button(this);back.setText("В комнату  ↗");back.setTextColor(Color.rgb(36,40,34));back.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(222,182,101)));
        back.setOnClickListener(v->{startActivity(new Intent(this,LauncherActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP));});bar.addView(back);
        frame.addView(bar);TextView origin=new TextView(this);origin.setTextColor(Color.rgb(166,169,155));origin.setPadding(24,0,24,8);origin.setText(Uri.parse(EmberRuntime.URLS.get(source)).getHost()+" · вход на сайте сервиса");frame.addView(origin);
        WebView web=runtime.view(this,source);
        if(web.getParent() instanceof ViewGroup)((ViewGroup)web.getParent()).removeView(web);
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onCreateWindow(WebView view,boolean isDialog,boolean userGesture,Message result){
                if(!userGesture)return false;
                Dialog dialog=new Dialog(HostActivity.this,android.R.style.Theme_Material_NoActionBar);
                LinearLayout body=new LinearLayout(HostActivity.this);body.setOrientation(LinearLayout.VERTICAL);body.setBackgroundColor(Color.rgb(19,25,29));
                TextView domain=new TextView(HostActivity.this);domain.setText("Вход в музыкальный сервис");domain.setTextColor(Color.rgb(242,225,185));domain.setPadding(20,16,20,16);body.addView(domain);
                WebView popup=new WebView(HostActivity.this);popup.getSettings().setJavaScriptEnabled(true);popup.getSettings().setDomStorageEnabled(true);popup.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
                CookieManager.getInstance().setAcceptThirdPartyCookies(popup,true);
                popup.setWebViewClient(new WebViewClient(){
                    @Override public void onPageFinished(WebView v,String url){domain.setText(Uri.parse(url).getHost());}
                    @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return !"https".equals(r.getUrl().getScheme());}
                });
                popup.setWebChromeClient(new WebChromeClient(){@Override public void onCloseWindow(WebView v){dialog.dismiss();popup.destroy();}});
                body.addView(popup,new LinearLayout.LayoutParams(-1,0,1));dialog.setContentView(body);dialog.getWindow().setLayout(-1,-1);dialog.show();
                ((WebView.WebViewTransport)result.obj).setWebView(popup);result.sendToTarget();return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request){
                String host=request.getOrigin().getHost();
                if(!EmberRuntime.MEDIA_HOSTS.contains(host)){request.deny();return;}
                java.util.List<String> resources=java.util.Arrays.asList(request.getResources());
                if(resources.size()==1&&resources.contains(PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID)){
                    runOnUiThread(()->new AlertDialog.Builder(HostActivity.this).setTitle("Защищённое воспроизведение")
                        .setMessage(host+" запрашивает разрешение для DRM-воспроизведения музыки.")
                        .setPositiveButton("Разрешить",(d,w)->request.grant(new String[]{PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID}))
                        .setNegativeButton("Отмена",(d,w)->request.deny()).show());
                }else request.deny();
            }
        });
        frame.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(frame);
    }
    // Keep service audio alive when the immersive renderer comes to the front.
    // No WebView.onPause()/pauseTimers() call here; foreground service owns it.
}
