"""Nocturne: quiet charcoal, brushed brass and a small pool of amber light.

Scoped, static GTK materials. Artwork, hardware pixbufs and the existing audio
reactive lamps retain their original pixels; the theme adds no animation loop.
"""
from functools import lru_cache
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
gi.require_version('GdkPixbuf','2.0')
from hardware_controls import pixbuf


CSS=b'''
.nocturne-theme { color: #e4d9c5; }
.nocturne-theme .card {
 background-color: #181a1b;
 background-image: linear-gradient(135deg,#232526,#181a1b 55%,#141617);
 box-shadow: inset 0 1px rgba(242,218,177,.075),inset 0 -1px rgba(2,3,3,.5);
}
window.ember-stage.nocturne-theme { background-color: #121414; }
window.ember-stage.nocturne-theme.stage-opening { background-color: transparent; }
.nocturne-theme .stage-opening-card { background-color: #181a1b; }
.nocturne-theme .title, .nocturne-theme .stage-track-title,
.nocturne-theme .stage-library-title, .nocturne-theme .stage-card-title,
.nocturne-theme .stage-artist-name, .nocturne-theme .stage-artist-section,
.nocturne-theme .stage-feature-title, .nocturne-theme .album-header-title,
.nocturne-theme .account-title, .nocturne-theme .dj-title,
.nocturne-theme .dj-request, .nocturne-theme .mashup-heading,
.nocturne-theme .mashup-track, .nocturne-theme .karaoke-control-title,
.nocturne-theme .editorial-title { color: #eee2cc; }
.nocturne-theme .artist, .nocturne-theme .stage-artist,
.nocturne-theme .stage-artist-prose, .nocturne-theme .stage-overview-story,
.nocturne-theme .album-header-artist, .nocturne-theme .editorial-body,
.nocturne-theme .dj-reply, .nocturne-theme .mashup-artist { color: #c5b6a0; }
.nocturne-theme .album, .nocturne-theme .time, .nocturne-theme .caption,
.nocturne-theme .stage-album, .nocturne-theme .stage-time,
.nocturne-theme .stage-overline, .nocturne-theme .stage-library-note,
.nocturne-theme .stage-card-subtitle, .nocturne-theme .stage-artist-summary,
.nocturne-theme .stage-artist-credit, .nocturne-theme .stage-feature-caption,
.nocturne-theme .album-header-metadata, .nocturne-theme .editorial-source,
.nocturne-theme .editorial-status, .nocturne-theme .mashup-subtitle,
.nocturne-theme .mashup-note, .nocturne-theme .mashup-field,
.nocturne-theme .dj-hint, .nocturne-theme .karaoke-hint,
.nocturne-theme .karaoke-control-label { color: #ab9b85; }
.nocturne-theme .eyebrow, .nocturne-theme .stage-brand,
.nocturne-theme .drawer-heading, .nocturne-theme .stage-library-source,
.nocturne-theme .stage-artist-kicker, .nocturne-theme .album-header-kicker,
.nocturne-theme .dj-frequency, .nocturne-theme .dj-understanding,
.nocturne-theme .dj-status, .nocturne-theme .dj-on-air,
.nocturne-theme .mashup-kicker, .nocturne-theme .mashup-status,
.nocturne-theme .editorial-kicker { color: #c3a16c; }
.nocturne-theme .stage-section-label, .nocturne-theme .mashup-source,
.nocturne-theme .dj-station-note { color: #b3a188; }
.nocturne-theme .cover-surface, .nocturne-theme .stage-art-shell {
 background-color: #101213;
 background-image: linear-gradient(140deg,rgba(190,194,195,.075),rgba(17,20,21,.58) 36%,rgba(3,5,6,.7) 80%,rgba(108,113,114,.06));
 box-shadow: inset 0 1px rgba(243,216,174,.14),inset 0 -1px rgba(230,195,140,.045),0 16px 34px rgba(0,0,0,.34);
}
.nocturne-theme .lamp-well {
 background-color: #0e1011;
 box-shadow: inset 1px 3px 7px rgba(0,0,0,.58),inset 0 -1px rgba(230,196,143,.045);
}
.nocturne-theme button.control, .nocturne-theme button.mini-button,
.nocturne-theme button.stage-transport {
 background-image: linear-gradient(140deg,#292c2d,#1b1e1f);
 color: #d7c6aa;
 box-shadow: inset 0 1px rgba(238,213,172,.065),2px 4px 8px rgba(0,0,0,.36);
}
.nocturne-theme button.control:hover, .nocturne-theme button.mini-button:hover,
.nocturne-theme button.stage-transport:hover {
 background-image: linear-gradient(140deg,#333637,#232526); color: #dfba7c;
}
.nocturne-theme button.control:active, .nocturne-theme button.mini-button:active,
.nocturne-theme button.stage-transport:active {
 background-image: linear-gradient(145deg,#151819,#252829);
 box-shadow: inset 1px 3px 5px rgba(0,0,0,.43),0 1px rgba(230,201,154,.04);
}
.nocturne-theme button.control:disabled, .nocturne-theme button.stage-transport:disabled {
 background-image: linear-gradient(140deg,#1e2122,#181a1b); color: #716451;
 box-shadow: inset 0 1px rgba(238,213,172,.025);
}
.nocturne-theme button.play, .nocturne-theme button.stage-transport.stage-play,
.nocturne-theme button.stage-accent, .nocturne-theme button.warm-button,
.nocturne-theme button.album-play-button {
 background-color: #b78b4d;
 background-image: linear-gradient(145deg,#dbb77c,#bc9458 55%,#a67b42);
 color: #241b12;
 box-shadow: inset 0 1px rgba(255,233,187,.35),inset 0 -1px rgba(62,36,12,.32),0 5px 13px rgba(0,0,0,.25);
}
.nocturne-theme button.play:hover, .nocturne-theme button.stage-transport.stage-play:hover,
.nocturne-theme button.stage-accent:hover, .nocturne-theme button.warm-button:hover,
.nocturne-theme button.album-play-button:hover {
 background-image: linear-gradient(145deg,#e7c68c,#c8a166); color: #241b12;
}
.nocturne-theme button.play:active, .nocturne-theme button.stage-transport.stage-play:active,
.nocturne-theme button.stage-accent:active, .nocturne-theme button.warm-button:active,
.nocturne-theme button.album-play-button:active {
 background-image: linear-gradient(145deg,#a37a42,#c29b60);
 box-shadow: inset 1px 3px 6px rgba(55,31,9,.32);
}
.nocturne-theme button.discovery-toggle, .nocturne-theme button.filter-chip,
.nocturne-theme button.mix-tile, .nocturne-theme .account-card,
.nocturne-theme button.stage-album, .nocturne-theme button.stage-add,
.nocturne-theme button.album-queue-button {
 background-color: #1b1e1f;
 background-image: linear-gradient(145deg,#252829,#181b1c);
 color: #c9b798; border-color: rgba(222,184,125,.09);
 box-shadow: inset 0 1px rgba(242,215,171,.035),1px 3px 7px rgba(0,0,0,.19);
}
.nocturne-theme button.discovery-toggle:hover, .nocturne-theme button.filter-chip:hover,
.nocturne-theme button.mix-tile:hover, .nocturne-theme button.stage-album:hover,
.nocturne-theme button.stage-add:hover, .nocturne-theme button.album-queue-button:hover {
 background-image: linear-gradient(145deg,#2c2f30,#202324); color: #e1c28f;
 border-color: rgba(222,184,125,.19);
}
.nocturne-theme button.filter-chip:checked, .nocturne-theme button.track-row.current-track {
 background-color: #232627; background-image: none; color: #d7b176;
 box-shadow: inset 1px 2px 4px rgba(0,0,0,.38),0 1px rgba(224,188,134,.04);
}
.nocturne-theme button.track-row:hover { background-color: #26292a; }
.nocturne-theme button.stage-quiet {
 background-color: rgba(185,189,190,.035); color: #c1af94;
 border-color: rgba(221,183,125,.095);
}
.nocturne-theme button.stage-quiet:hover {
 background-color: rgba(185,189,190,.075); color: #e3cfab;
}
.nocturne-theme .stage-nav { background-color: rgba(8,10,11,.65); }
.nocturne-theme button.stage-tab { color: #a99b86; }
.nocturne-theme button.stage-tab:checked {
 background-image: linear-gradient(145deg,#2a2d2e,#1d2021); color: #ddbb81;
 box-shadow: inset 0 1px rgba(236,204,155,.07);
}
.nocturne-theme .stage-console {
 background-image: linear-gradient(145deg,rgba(30,33,34,.96),rgba(18,20,21,.97));
 border-color: rgba(229,195,144,.065);
 box-shadow: inset 0 1px rgba(241,211,168,.055),0 8px 26px rgba(0,0,0,.25);
}
.nocturne-theme .progress trough, .nocturne-theme scale trough,
.nocturne-theme .dj-micro-level trough {
 background-color: #090b0c; background-image: none;
 box-shadow: inset 0 1px 3px rgba(0,0,0,.5);
}
.nocturne-theme .progress progress, .nocturne-theme scale highlight,
.nocturne-theme .editorial-progress progress, .nocturne-theme .dj-micro-level progress {
 background-image: linear-gradient(to right,#866338,#c9a065); background-color: #bf955a;
 box-shadow: none; border: none;
}
.nocturne-theme scale slider { background-color: #cda66b; }
.nocturne-theme entry.stage-search, .nocturne-theme entry.track-search,
.nocturne-theme entry.dj-entry {
 background-color: #0d0f10; background-image: linear-gradient(to bottom,#0d0f10,#151819);
 color: #e5d6bb; border-color: rgba(223,183,123,.11);
 box-shadow: inset 0 2px 5px rgba(0,0,0,.32),0 1px rgba(237,208,162,.025);
}
.nocturne-theme entry.stage-search:focus, .nocturne-theme entry.track-search:focus,
.nocturne-theme entry.dj-entry:focus { border-color: rgba(201,155,86,.5); }
.nocturne-theme .record-panel { background-color: rgba(10,12,13,.55); border-color: rgba(223,184,126,.075); }
.nocturne-theme .record-header { background-color: rgba(189,192,193,.025); }
.nocturne-theme .record-heading, .nocturne-theme .record-rank { color: #9d8a6d; }
.nocturne-theme .record-title label { color: #e5d7bd; }
.nocturne-theme .record-current .record-title label { color: #dbb77d; }
.nocturne-theme .record-artist label, .nocturne-theme label.record-artist,
.nocturne-theme .record-album, .nocturne-theme .record-duration { color: #b8a78b; }
.nocturne-theme .record-title:hover label, .nocturne-theme .record-artist:hover label { color: #e9c58b; }
.nocturne-theme .record-row:disabled .record-title label,
.nocturne-theme .record-row:disabled .record-artist label,
.nocturne-theme .record-title:disabled label { color: #83735c; }
.nocturne-theme button.record-action {
 background-image: linear-gradient(145deg,#252829,#181b1c); color: #c8af86;
 border-color: rgba(222,184,125,.075); box-shadow: inset 0 1px rgba(241,211,168,.025);
}
.nocturne-theme button.record-action:hover { color: #dfbc80; border-color: rgba(218,171,103,.22); }
.nocturne-theme button.record-action:disabled { color: #716149; background-image: none; }
.nocturne-theme .record-list row.record-row,
.nocturne-theme .stage-track-row { background-color: rgba(12,14,15,.38); }
.nocturne-theme .record-list row.record-row:hover { background-color: rgba(174,177,178,.045); }
.nocturne-theme .record-list row.record-row.record-current,
.nocturne-theme .dj-track.dj-current {
 background-color: rgba(78,83,84,.13); border-color: rgba(208,163,96,.23);
}
.nocturne-theme .stage-queue-current, .nocturne-theme .stage-overview-panel,
.nocturne-theme .stage-artist-reading, .nocturne-theme .editorial-card,
.nocturne-theme .dj-desk, .nocturne-theme .karaoke-panel,
.nocturne-theme .mashup-hero, .nocturne-theme .mashup-deck,
.nocturne-theme .mashup-deck-b {
 background-color: #191c1d;
 background-image: linear-gradient(135deg,rgba(34,37,38,.8),rgba(18,21,21,.94));
 border-color: rgba(222,183,123,.075);
 box-shadow: inset 0 1px rgba(240,211,168,.045),0 6px 18px rgba(0,0,0,.17);
}
.nocturne-theme .stage-artist-banner, .nocturne-theme .album-header { background-color: #141718; border-color: rgba(222,183,123,.09); }
.nocturne-theme .stage-artist-banner.stage-artist-capture,
.nocturne-theme .stage-artist-hero.stage-artist-banner-content { background-color: transparent; background-image: none; }
.nocturne-theme .album-cover-mount {
 background-image: linear-gradient(145deg,rgba(194,198,199,.075),rgba(6,8,9,.75));
 border-color: rgba(229,194,141,.15);
 box-shadow: inset 0 1px rgba(236,206,163,.075),0 10px 22px rgba(0,0,0,.38);
}
.nocturne-theme .stage-artist-chip, .nocturne-theme .editorial-language {
 background-color: rgba(9,11,12,.32); color: #c6af86; border-color: rgba(218,177,115,.1);
}
.nocturne-theme .dj-preferences, .nocturne-theme .mashup-settings,
.nocturne-theme .karaoke-control-well { background-color: rgba(8,10,11,.42); border-color: rgba(218,177,115,.07); }
.nocturne-theme .dj-track, .nocturne-theme .mashup-row {
 background-color: #121516; background-image: linear-gradient(to right,rgba(25,28,29,.88),rgba(12,15,15,.83));
 border-color: rgba(218,177,115,.045);
}
.nocturne-theme button.editorial-translate,
.nocturne-theme .mashup-view combobox button, .nocturne-theme .karaoke-panel combobox button,
.nocturne-theme .scene-control combobox button {
 background-image: linear-gradient(to bottom,#2a2d2e,#1c1f20); color: #d6bd94;
 border-color: rgba(224,185,127,.105); box-shadow: inset 0 1px rgba(241,211,168,.04);
}
.nocturne-theme .mashup-view combobox cellview { color: #d6bd94; }
.nocturne-theme .mashup-deck spinbutton, .nocturne-theme .mashup-settings spinbutton {
 background-image: linear-gradient(to bottom,#0d1011,#171a1b); background-color: #121516;
 color: #d8c19a; border-color: rgba(218,177,115,.1);
}
.nocturne-theme .mashup-deck spinbutton entry, .nocturne-theme .mashup-settings spinbutton entry { color: #d8c19a; }
.nocturne-theme .mashup-deck spinbutton button, .nocturne-theme .mashup-settings spinbutton button {
 background-image: linear-gradient(to bottom,#252829,#1d2021); color: #c7a66f;
}
.nocturne-theme .mashup-settings checkbutton, .nocturne-theme .scene-control checkbutton { color: #c4b292; }
.nocturne-theme .mashup-settings checkbutton check, .nocturne-theme .scene-control checkbutton check {
 background-image: linear-gradient(to bottom,#0d1011,#232526); border-color: #695031; color: #d4ac6b;
}
.nocturne-theme .mashup-settings checkbutton check:checked {
 background-image: linear-gradient(to bottom,#cba66d,#96703d); color: #21180f;
}
.nocturne-theme entry.mashup-name { color: #e0cba8; }
.nocturne-theme .karaoke-current, .nocturne-theme button.stage-line.stage-line-active { color: #f1dfbd; text-shadow: none; }
.nocturne-theme .karaoke-neighbour, .nocturne-theme button.stage-line.stage-line-past { color: #a4947b; }
.nocturne-theme button.stage-line { color: #776a57; }
.nocturne-theme button.stage-line:hover { color: #ccba98; }
.nocturne-theme .karaoke-divider, .nocturne-theme .editorial-rule { background-color: rgba(215,175,112,.07); }
.nocturne-theme.settings-popover, .nocturne-theme .settings-popover,
.nocturne-theme.source-popover, .nocturne-theme .source-popover,
.nocturne-theme.scene-popover, .nocturne-theme .scene-popover,
.nocturne-theme.ember-quality-popover, .nocturne-theme .ember-quality-popover {
 background-color: #191c1d; background-image: none; color: #d8c6a7;
 border-color: #343a3c; box-shadow: none;
}
.nocturne-theme.settings-popover button.settings-action {
 background-image: linear-gradient(145deg,#272a2b,#1a1d1e); color: #d1b68c;
 border: none; box-shadow: inset 0 1px rgba(236,205,158,.04);
}
.nocturne-theme .theme-choice { background-color: #151819; border-color: rgba(211,170,108,.13); }
.nocturne-theme .theme-choice-title { color: #dfc399; }
.nocturne-theme .theme-choice-note { color: #ad9877; }
.nocturne-theme .theme-choice switch { background: #101314; border-color: #4e3b23; }
.nocturne-theme .theme-choice switch:checked { background: #7e5c32; border-color: #ad8147; }
.nocturne-theme .theme-choice switch slider { background-image: linear-gradient(145deg,#d8bb89,#9e7c46); }
.nocturne-theme .scene-control .scene-title, .nocturne-theme .ember-quality-name { color: #e9d5b2; }
.nocturne-theme .scene-control .scene-subtitle, .nocturne-theme .scene-control .caption,
.nocturne-theme .ember-quality-note, .nocturne-theme .ember-quality-heading { color: #b7a383; }
.nocturne-theme .scene-control .headphone-tuning label, .nocturne-theme .ember-quality-detail { color: #d4c1a0; }
.nocturne-theme .scene-control button.scene-choice {
 background-image: linear-gradient(145deg,#252829,#1a1d1e); color: #ba9e74;
 border-color: rgba(224,185,127,.075); box-shadow: inset 0 1px rgba(241,211,168,.035),1px 3px 6px rgba(0,0,0,.2);
}
.nocturne-theme .scene-control button.scene-choice:checked {
 background-image: linear-gradient(145deg,#303334,#242627); color: #dcba80; border-color: rgba(205,155,83,.24);
 box-shadow: inset 1px 2px 5px rgba(0,0,0,.28),0 1px rgba(241,211,168,.035);
}
.nocturne-theme button.ember-quality {
 background-image: linear-gradient(165deg,rgba(216,219,220,.115),rgba(116,120,121,.07) 48%,rgba(58,62,63,.13));
 background-color: rgba(64,68,69,.045); color: #d8c3a0;
 border-color: rgba(226,198,154,.18); box-shadow: inset 0 1px rgba(240,214,174,.095);
}
.nocturne-theme button.ember-quality:hover { color: #ebd9b7; border-color: rgba(226,198,154,.29); }
.nocturne-theme.favorite-note {
 background-color: #191c1d; background-image: linear-gradient(145deg,#252829,#171a1b);
 border-color: rgba(218,184,132,.14); color: #e4d9c5;
}
.nocturne-theme button.ember-heart:hover { background-color: rgba(204,166,112,.035); }
.nocturne-theme button.ember-flow.ember-flow-lamp {
 background-image: linear-gradient(to bottom,#0f1213,#1b1e1f);
 color: #a68d66; border-color: rgba(2,4,5,.65);
 box-shadow: inset 0 2px 4px rgba(0,0,0,.55),0 1px rgba(228,190,132,.06);
}
.nocturne-theme button.ember-flow.ember-flow-lamp:checked {
 background-image: linear-gradient(to bottom,#151819,#232627); color: #d4b17a;
}
.theme-choice.night-choice { background-color: #151819; border-color: rgba(211,170,108,.13); }
.theme-choice.night-choice .theme-choice-title { color: #dfc399; }
.theme-choice.night-choice .theme-choice-note { color: #ad9877; }
.theme-choice.night-choice switch { background: #101314; border-color: #4e3b23; }
.theme-choice.night-choice switch:checked { background: #7e5c32; border-color: #ad8147; }
.theme-choice.night-choice switch slider { background-image: linear-gradient(145deg,#d8bb89,#9e7c46); }
'''


@lru_cache(maxsize=1)
def preview():
    """A small code-native material sample, prepared once for theme settings."""
    return pixbuf('''<svg xmlns="http://www.w3.org/2000/svg" width="222" height="86" viewBox="0 0 222 86">
      <defs>
        <linearGradient id="body" x1="0" y1="0" x2="1" y2="1">
          <stop stop-color="#232526"/><stop offset=".5" stop-color="#141718"/><stop offset="1" stop-color="#090b0c"/>
        </linearGradient>
        <radialGradient id="light"><stop stop-color="#bf8a44" stop-opacity=".12"/>
          <stop offset=".5" stop-color="#78502b" stop-opacity=".045"/><stop offset="1" stop-color="#151819" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="brass" x1="0" y1="0" x2="1" y2="1">
          <stop stop-color="#414546"/><stop offset=".4" stop-color="#242728"/><stop offset="1" stop-color="#151819"/>
        </linearGradient>
      </defs>
      <rect x=".5" y=".5" width="221" height="85" rx="13" fill="url(#body)" stroke="#6b7274" stroke-opacity=".2"/>
      <ellipse cx="181" cy="35" rx="70" ry="61" fill="url(#light)"/>
      <circle cx="183" cy="43" r="27" fill="#090c0d" stroke="#b58a51" stroke-opacity=".24"/>
      <circle cx="183" cy="43" r="23.5" fill="url(#brass)" stroke="#d7af73" stroke-opacity=".12"/>
      <circle cx="183" cy="43" r="19" fill="#1b1e1f" stroke="#e2bd83" stroke-opacity=".08"/>
      <path d="M183 25v5" stroke="#d6af72" stroke-width="1.4" stroke-linecap="round"/>
      <path d="M12 1h198" stroke="#ead0a9" stroke-opacity=".07"/>
      <path d="M14 75h106" stroke="#cd9a56" stroke-opacity=".14"/>
      <path d="M14 75h38" stroke="#cd9a56" stroke-opacity=".5"/>
    </svg>''',222,86)
