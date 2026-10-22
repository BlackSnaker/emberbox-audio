"""Match only the selected application's output, never the system monitor."""
from dataclasses import dataclass
from pathlib import Path
import re
from sources import browser_family


@dataclass(frozen=True)
class Target:
    source: str = 'spotify'
    pid: int = 0
    family: str = ''
    player: str = ''
    processed: bool = False


def descendant(pid, owner):
    if not pid or not owner:
        return False
    seen = set()
    while pid > 1 and pid not in seen:
        if pid == owner:
            return True
        seen.add(pid)
        try:
            # comm may contain spaces or parentheses; PPID follows its final ')'.
            pid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return False
    return False


def matches(props, target):
    # The karaoke return stream is a descendant of Emberbox for native YouTube.
    # Never capture, reroute or apply the source volume to it a second time.
    if str(props.get('emberbox.karaoke','')).lower()=='true':
        try:pid=int(props.get('application.process.id',props.get('pipewire.sec.pid',0)))
        except (TypeError,ValueError):pid=0
        return bool(target and target.player and target.processed and descendant(pid,target.pid))
    if target and target.processed:return False
    if not target or not target.player:
        return False
    values = [str(props.get(key, '')).lower() for key in
              ('application.name', 'application.process.binary', 'application.id', 'node.name')]
    if target.source == 'spotify':
        return any(value in ('spotify', 'com.spotify.client') or
                   re.fullmatch(r'spotify-\d+', value) for value in values)
    try:
        pid = int(props.get('application.process.id', props.get('pipewire.sec.pid', 0)))
    except (ValueError, TypeError):
        pid = 0
    if descendant(pid, target.pid):
        return True
    # Sandboxed browsers can expose a D-Bus proxy PID. In that case the
    # finest available Pulse/PipeWire boundary is the browser application.
    try:
        executable = Path(f'/proc/{target.pid}/exe').resolve().name
    except OSError:
        executable = ''
    if browser_family(executable) == target.family:
        return False  # real host PID: never broaden to other browser instances
    return bool(target.family and browser_family(*values) == target.family)


def output_nodes(graph, target):
    clients = {str(item['id']): item.get('info', {}).get('props', {})
               for item in graph if item.get('type') == 'PipeWire:Interface:Client'}
    return {str(item['id']) for item in graph
            if item.get('type') == 'PipeWire:Interface:Node'
            and item.get('info', {}).get('props', {}).get('media.class') == 'Stream/Output/Audio'
            and matches({**clients.get(str(item.get('info', {}).get('props', {}).get('client.id')), {}),
                         **item.get('info', {}).get('props', {})}, target)}
