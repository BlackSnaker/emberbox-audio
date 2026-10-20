"""Small Grunesphism terminal presentation, readable in logs and without color."""
import locale
import os
import re
import shlex
import sys


class Terminal:
    def __init__(self, *, language='auto', plain=False, stream=None, environ=None):
        self.stream=stream or sys.stdout
        env=os.environ if environ is None else environ
        lang=env.get('LC_ALL') or env.get('LC_MESSAGES') or env.get('LANG','')
        self.ru=language=='ru' or language=='auto' and lang.lower().startswith('ru')
        self.color=not plain and self.stream.isatty() and env.get('TERM')!='dumb' and 'NO_COLOR' not in env
        encoding=getattr(self.stream,'encoding',None) or locale.getpreferredencoding(False)
        try:'✓ ↓ ─'.encode(encoding);self.unicode=not plain
        except (UnicodeError,LookupError):self.unicode=False

    def text(self, en, ru):return ru if self.ru else en

    def paint(self, value, tone='cream'):
        colors={'cream':'235;219;178','amber':'215;153;33','green':'142;192;124',
                'muted':'168;153;132','red':'251;73;52'}
        return f'\033[38;2;{colors[tone]}m{value}\033[0m' if self.color else value

    def write(self, value=''):
        # Paths/environment data must not inject terminal control sequences.
        value=re.sub(r'[\x00-\x08\x0b-\x1f\x7f]',lambda m:'?' if m[0]!='\x1b' else '',str(value)) if not self.color else str(value)
        print(value,file=self.stream,flush=True)

    def banner(self, version):
        self.write()
        self.write(self.paint('  E M B E R B O X   A U D I O','amber')+'  '+self.paint(version,'muted'))
        self.write('  '+self.paint(self.text('A little warmth. From the first step.','Немного тепла. С первого шага.'),'cream'))
        self.write('  '+self.paint(('─' if self.unicode else '-')*48,'muted'))

    def step(self, number, en, ru):
        self.write();self.write(self.paint(f'  {number}/5  ','amber')+self.paint(self.text(en,ru)))

    def item(self, value, good=True):
        mark=('✓' if good else '↓') if self.unicode else ('OK' if good else '+')
        self.write('    '+self.paint(mark,'green' if good else 'amber')+'  '+str(value))

    def note(self, en, ru):self.write('    '+self.paint(self.text(en,ru),'muted'))
    def warning(self, en, ru):self.write('    '+self.paint('! '+self.text(en,ru),'amber'))
    def error(self, en, ru):self.write('    '+self.paint('! '+self.text(en,ru),'red'))
    def command(self, command):self.write('    '+self.paint('$ '+shlex.join(map(str,command)),'amber'))

    def success(self, en, ru):
        self.write();self.item(self.text(en,ru));self.write()
