package io.emberbox.quest;

import android.app.*;
import android.content.*;
import android.media.MediaMetadata;
import android.media.session.*;
import android.os.*;
import org.json.JSONObject;

/** Own media session keeps provider playback alive behind the immersive room. */
public class PlaybackService extends Service {
    private static PlaybackService instance;
    private MediaSession session;
    @Override public void onCreate(){
        super.onCreate();instance=this;
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("ember-playback","Ember Quest · музыка",NotificationManager.IMPORTANCE_LOW));
        Intent launch=new Intent(this,LauncherActivity.class);
        PendingIntent content=PendingIntent.getActivity(this,0,launch,PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,PlaybackService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        Notification notification=new Notification.Builder(this,"ember-playback").setSmallIcon(android.R.drawable.ic_media_play).setContentTitle("Ember Quest").setContentText("Музыка в твоей комнате").setContentIntent(content).addAction(new Notification.Action.Builder(null,"Закрыть",stop).build()).setOngoing(true).build();
        startForeground(1783,notification);
        session=new MediaSession(this,"Ember Quest");session.setCallback(new MediaSession.Callback(){
            @Override public void onPlay(){EmberRuntime.ensure(PlaybackService.this).transport("resume");}
            @Override public void onPause(){EmberRuntime.ensure(PlaybackService.this).transport("pause");}
            @Override public void onSkipToNext(){EmberRuntime.ensure(PlaybackService.this).transport("next");}
            @Override public void onSkipToPrevious(){EmberRuntime.ensure(PlaybackService.this).transport("previous");}
        });session.setActive(true);
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){if(intent!=null&&"stop".equals(intent.getAction())){EmberRuntime.shutdown();stopSelf();}return START_NOT_STICKY;}
    public static void refresh(JSONObject state){PlaybackService owner=instance;if(owner==null||owner.session==null)return;
        owner.session.setMetadata(new MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE,state.optString("title")).putString(MediaMetadata.METADATA_KEY_ARTIST,state.optString("artist")).putString(MediaMetadata.METADATA_KEY_ALBUM,state.optString("album")).build());
        owner.session.setPlaybackState(new PlaybackState.Builder().setActions(PlaybackState.ACTION_PLAY|PlaybackState.ACTION_PAUSE|PlaybackState.ACTION_SKIP_TO_NEXT|PlaybackState.ACTION_SKIP_TO_PREVIOUS).setState(state.optBoolean("playing")?PlaybackState.STATE_PLAYING:PlaybackState.STATE_PAUSED,(long)(state.optDouble("position",0)*1000),state.optBoolean("playing")?1:0).build());
    }
    @Override public void onDestroy(){if(session!=null)session.release();instance=null;super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
