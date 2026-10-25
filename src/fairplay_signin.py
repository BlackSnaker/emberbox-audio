"""Manual sign-in window for the isolated FairPlay research worker."""
import json,os,subprocess,sys,threading,time,resource,ctypes
from pathlib import Path
from source_picker import text
from fairplay_setup import prepare,configured
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,GLib
os.umask(0o077)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
if ctypes.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError("DUMP_PROTECTION")
ROOT=Path(__file__).resolve().parent

MESSAGES={'Проверяем загрузку движка…': 'Preparing the audio engine…', 'Движок загружен. Можно войти.': 'The engine is ready. Sign in to continue.', 'Подключаемся к Apple…': 'Connecting to Apple…', 'Запрос входа передан Apple. Ожидаем ответ…': 'Sign-in request sent. Waiting for Apple…', 'Apple запрашивает код с доверенного устройства.': 'Apple needs a code from your trusted device.', 'Движок не получил ответ на запрос входа.': 'The engine did not receive a sign-in response.', 'Вход не завершён. Пароль не сохранён.': 'Sign-in did not complete. Your password was not saved.', 'Apple вернула ошибку входа.': 'Apple returned a sign-in error.', 'Процесс подключения завершился с ошибкой.': 'The connection process failed.', 'Apple запрашивает дополнительный диалог. Этот шаг требует доработки подключения.': 'Apple requested an unsupported dialog.', 'Вход не завершён. Код ошибки сохранён без данных аккаунта.': 'Sign-in did not complete.', 'Введённые данные превышают длину, поддерживаемую движком.': 'The input exceeds the engine’s supported length.', 'Процесс подключения остановился.': 'The connection process stopped.', 'Процесс проверки остановился. Действующий плеер продолжает работать.': 'The connection process stopped. The player remains available.', 'Apple не ответила вовремя. Проверка остановлена без повторной отправки данных.': 'Apple did not respond in time. No credentials were resubmitted.'}

def translated(message):
 return text(MESSAGES.get(message,message),message)

class Window(Gtk.Window):
 def __init__(self):
  super().__init__(title='Ember · Apple Lossless')
  self.set_default_size(560,460);self.set_position(Gtk.WindowPosition.CENTER)
  self.connect('destroy',self.close)
  css=Gtk.CssProvider();css.load_from_data(b'''window {background:#282828;color:#ebdbb2;} label {color:#ebdbb2;} .brand{color:#d79921;font-size:11px;letter-spacing:3px;} .title{font-size:27px;font-weight:bold;} .note{color:#bdae93;font-size:12px;} entry{background:#1d2021;color:#fbf1c7;border:1px solid #504945;border-radius:12px;padding:10px;} button{background-image:none;background:#d79921;color:#1d2021;border:0;border-radius:13px;padding:11px;font-weight:bold;} button:disabled{background:#504945;color:#a89984;} .status{color:#fabd2f;}''')
  Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16,margin=28);self.add(box)
  def label(value,style):
   widget=Gtk.Label(label=value,xalign=0);widget.set_line_wrap(True);widget.set_max_width_chars(56);widget.get_style_context().add_class(style);box.pack_start(widget,False,False,0);return widget
  label('E M B E R   /   L O S S L E S S','brand')
  label(text('Every detail, closer','Музыка в каждой детали'),'title')
  label(text('Optional native Lossless and Hi-Res playback. Sign in to Apple Music for this audio engine; your library stays in Ember.','Нативный звук Lossless и Hi-Res. Для этого аудиодвижка нужен отдельный вход в Apple Music; медиатека остаётся в Ember.'),'note')
  self.user=Gtk.Entry(placeholder_text='Apple ID');box.pack_start(self.user,False,False,0)
  self.password=Gtk.Entry(placeholder_text=text('Apple ID password','Пароль Apple ID'));self.password.set_visibility(False);self.password.set_input_purpose(Gtk.InputPurpose.PASSWORD);box.pack_start(self.password,False,False,0)
  self.code=Gtk.Entry(placeholder_text=text('Verification code · 6 digits','Код подтверждения · 6 цифр'));self.code.set_max_length(6);self.code.set_input_purpose(Gtk.InputPurpose.DIGITS);box.pack_start(self.code,False,False,0);self.code.set_no_show_all(True)
  self.button=Gtk.Button(label=text('Connect Lossless','Подключить Lossless'));self.button.set_sensitive(False);self.button.connect('clicked',self.submit);box.pack_start(self.button,False,False,0)
  self.status=label(translated('Проверяем загрузку движка…'),'status')
  label(text('Password and code stay in this sign-in process and are never logged. Browser sign-in is separate.','Пароль и код остаются в процессе входа и не записываются в журнал. Вход в браузере выполняется отдельно.'),'note')
  self.failed=False;self.deadline=None;self.mode='login';self.process=None;self.connected=False
  self.password.connect('activate',lambda *_:self.submit());self.code.connect('activate',lambda *_:self.submit())
  GLib.timeout_add_seconds(1,self.watchdog);self.show_all();threading.Thread(target=self.prepare,daemon=True).start()
 def set_status(self,value):
  self.status.set_text(translated(value))
 def prepare(self):
  try:
   from spatial_setup import prepare as prepare_spatial,configured as spatial_configured
   if not spatial_configured():prepare_spatial(lambda message:GLib.idle_add(self.set_status,message))
   if not configured():prepare(lambda message:GLib.idle_add(self.set_status,message))
   GLib.idle_add(self.start_worker)
  except Exception:
   GLib.idle_add(self.set_status,text('Setup failed. Run install.sh --apple-lossless in a terminal for details.','Подготовка не завершена. Запусти install.sh --apple-lossless в терминале для проверки.'))
 def start_worker(self):
  if self.mode=='closed':return False
  self.process=subprocess.Popen([sys.executable,str(ROOT/'fairplay_auth_worker.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
  threading.Thread(target=self.read,daemon=True).start();return False
 def read(self):
  for line in self.process.stdout:
   try:value=json.loads(line)
   except Exception:continue
   GLib.idle_add(self.event,value)
  GLib.idle_add(self.exited)
 def event(self,value):
  event=value.get('event')
  if event=='ready':self.set_status('Движок загружен. Можно войти.');self.button.set_sensitive(True)
  elif event=='authenticating':self.deadline=time.monotonic()+90;self.set_status('Подключаемся к Apple…')
  elif event=='credentials-requested':self.set_status('Запрос входа передан Apple. Ожидаем ответ…')
  elif event=='code-needed':
   self.deadline=time.monotonic()+180;self.mode='code';self.code.show();self.code.grab_focus();self.button.set_label(text('Confirm code','Подтвердить код'));self.button.set_sensitive(True);self.set_status('Apple запрашивает код с доверенного устройства.')
  elif event=='signed-in':
   self.deadline=None;self.mode='done';self.connected=True;self.code.hide();self.user.hide();self.password.hide();self.button.set_label(text('Ready · return to Ember','Готово · вернуться в Ember'));self.button.set_sensitive(True);self.set_status(text('Signed in. The playing track will confirm its actual quality.','Вход выполнен. Формат подтвердится при воспроизведении трека.'))
  elif event=='diagnostic':
   stage=value.get('stage')
   messages={'auth-response-absent':'Движок не получил ответ на запрос входа.','login-rejected':'Вход не завершён. Пароль не сохранён.','apple-auth':'Apple вернула ошибку входа.','native-exception':'Процесс подключения завершился с ошибкой.'}
   if stage in messages:self.set_status(translated(messages[stage])+(text(' Code: ',' Код: ')+str(value['code']) if 'code' in value else ''))
  elif event=='dialog':
   self.deadline=time.monotonic()+180
   data=value.get('dialog',{});dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,buttons=Gtk.ButtonsType.NONE,text=str(data.get('title','Apple')))
   dialog.format_secondary_text(str(data.get('message','')))
   for i,title in enumerate(data.get('buttons',[])[:8]):dialog.add_button(str(title),i)
   choice=dialog.run();dialog.destroy()
   if choice>=0:
    try:self.process.stdin.write(json.dumps({'action':'dialog','selection':choice})+'\n');self.process.stdin.flush()
    except Exception:pass
   else:self.process.terminate()
  elif event=='dialog-required':self.failed=True;self.set_status('Apple запрашивает дополнительный диалог. Этот шаг требует доработки подключения.');self.button.set_sensitive(False)
  elif event in ('sign-in-failed','error'):
   self.deadline=None;self.failed=True;self.set_status(text('Sign-in did not complete.','Вход не завершён.'));self.button.set_sensitive(False)
  return False
 def submit(self,*args):
  if not self.button.get_sensitive():return
  if self.mode=='done':self.close();return
  if self.mode=='login':
   user=self.user.get_text().strip();password=self.password.get_text()
   if not user or not password:return
   if len(user.encode())>250 or len(password.encode())>239:self.set_status('Введённые данные превышают длину, поддерживаемую движком.');return
   value={'action':'login','username':user,'password':password};self.password.set_text('');self.user.set_sensitive(False);self.password.set_sensitive(False)
  elif self.mode=='code':
   code=self.code.get_text()
   if len(code)!=6 or not code.isascii() or not code.isdigit():return
   value={'action':'code','code':code};self.code.set_text('')
  else:return
  self.button.set_sensitive(False)
  try:self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush()
  except Exception:self.set_status('Процесс подключения остановился.')
 def exited(self):
  if self.mode!='done' and not self.failed:self.set_status('Процесс проверки остановился. Действующий плеер продолжает работать.');self.button.set_sensitive(False)
  return False
 def watchdog(self):
  if self.deadline is not None and time.monotonic()>self.deadline:
   self.deadline=None;self.failed=True;self.button.set_sensitive(False);self.set_status('Apple не ответила вовремя. Проверка остановлена без повторной отправки данных.')
   if self.process and self.process.poll() is None:self.process.terminate()
  return True
 def close(self,*args):
  self.mode='closed'
  if self.process and self.process.poll() is None:self.process.terminate()
  Gtk.main_quit()

window=Window();Gtk.main();raise SystemExit(0 if window.connected else 1)
