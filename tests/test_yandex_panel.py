"""Playlist rendering regression tests, without a display or live account."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import gi
gi.require_version('Gtk', '3.0')
import yandex_panel


class YandexPanelTests(unittest.TestCase):
    def render(self, items):
        panel = SimpleNamespace(content=Mock(), artwork=Mock(), notice=Mock(),
                                category='tracks', play_track=Mock(), open_playlist=Mock())
        panel.player=SimpleNamespace(state={'id':'74'})
        panel.update_current=lambda ident:yandex_panel.YandexPanel.update_current(panel,ident)
        buttons = [Mock() for _ in items]
        with patch.object(yandex_panel, 'clear'), patch.object(yandex_panel, 'label'), \
             patch.object(yandex_panel.Gtk, 'Button', side_effect=buttons), \
             patch.object(yandex_panel.Gtk, 'Box'), patch.object(yandex_panel.Gtk, 'Image'):
            yandex_panel.YandexPanel.render(panel, items)
        return panel, buttons

    def test_long_playlist_renders_and_passes_every_track_to_playback(self):
        items = [{'id': str(i), 'title': 'Track ' + str(i), 'kind': 'song'} for i in range(125)]
        panel, buttons = self.render(items)
        self.assertEqual(len(panel.track_buttons), 125)
        self.assertEqual(panel.content.pack_start.call_count, 125)
        # The last row must be clickable, and its context must include the tail.
        callback = buttons[-1].connect.call_args.args[1]
        callback(buttons[-1])
        ident, context = panel.play_track.call_args.args
        self.assertEqual(ident, '124')
        self.assertEqual([v['id'] for v in context], [v['id'] for v in items])
        self.assertEqual(context[-1]['uri'], 'yandex:track:124')

    def test_current_track_is_highlighted_on_open_and_on_track_change(self):
        items=[{'id':'74','title':'Current'},{'id':'75','title':'Next'},
               {'id':'74','title':'Playlist, not a track','kind':'playlist'}]
        panel,buttons=self.render(items)
        buttons[0].get_style_context.return_value.add_class.assert_any_call('current-track')
        buttons[1].get_style_context.return_value.remove_class.assert_any_call('current-track')
        for button in buttons:button.get_style_context.return_value.reset_mock()
        panel.update_current('75')
        buttons[0].get_style_context.return_value.remove_class.assert_called_once_with('current-track')
        buttons[1].get_style_context.return_value.add_class.assert_called_once_with('current-track')
        buttons[2].get_style_context.return_value.add_class.assert_not_called()
        panel.update_current(None)
        buttons[1].get_style_context.return_value.remove_class.assert_called_with('current-track')

    def test_wave_status_distinguishes_origin_and_pause(self):
        with patch.object(yandex_panel,'text',side_effect=lambda en,ru:en):
            state={'wave':True,'playing':True,'waveKind':'playlist'}
            self.assertIn('Wave from playlist',yandex_panel.wave_description(state))
            state.update(waveKind='track',waveTitle='Original seed')
            self.assertIn('Wave from track — Original seed',yandex_panel.wave_description(state))
            state['playing']=False
            self.assertIn('Paused',yandex_panel.wave_description(state))
            state.update(waveKind='personal',waveTitle='')
            self.assertIn('My Wave',yandex_panel.wave_description(state))
            state['wave']=False
            self.assertEqual(yandex_panel.wave_description(state),'')

    def test_track_wave_button_uses_current_track_not_playlist_id(self):
        panel=SimpleNamespace(player=SimpleNamespace(state={'id':'74','title':'Selected song'}),request=Mock())
        yandex_panel.YandexPanel.start_track_wave(panel)
        panel.request.assert_called_once_with('wave',trackId='74',title='Selected song')
        panel.request.reset_mock();panel.player.state={}
        yandex_panel.YandexPanel.start_track_wave(panel)
        panel.request.assert_not_called()

    def test_playlist_cards_beyond_fifty_are_also_accessible(self):
        items = [{'id': '42:' + str(i), 'title': 'Playlist', 'kind': 'playlist'} for i in range(60)]
        panel, buttons = self.render(items)
        self.assertEqual(len(buttons), len(panel.track_buttons))
        callback = buttons[-1].connect.call_args.args[1]
        callback(buttons[-1])
        panel.open_playlist.assert_called_once_with('42:59')


if __name__ == '__main__':
    unittest.main()
