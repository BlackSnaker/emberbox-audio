"""Clear artist-room glass over a shallow, warm physical chassis.

These static materials reuse the existing GTK/Cairo cache and finite hover
transitions. No live blur, full-window opacity or additional frame clock.
All rules are confined to the artist; the album room retains its own material.
"""
CSS=b'''
.ember-stage .artist-glass-room .stage-overview-panel,
.ember-stage .artist-glass-room .stage-artist-reading,
.ember-stage .artist-glass-room .editorial-card {
 background-color: rgba(12,19,21,.34);
 background-image: linear-gradient(118deg,rgba(246,216,181,.065),rgba(246,242,226,0) 33%,rgba(182,220,238,.025) 76%,rgba(233,205,232,.045)),
                   linear-gradient(to bottom,rgba(255,248,229,.055),rgba(255,248,229,0) 20%,rgba(195,212,226,0) 83%,rgba(195,212,226,.025));
 border-color: rgba(219,228,225,.105); border-top-color: rgba(255,239,207,.24);
 border-left-color: rgba(191,225,234,.18); border-right-color: rgba(235,208,222,.13);
 border-bottom-color: rgba(192,205,221,.10);
 box-shadow: inset 0 1px 1px rgba(255,247,219,.045),inset 0 -1px 2px rgba(7,12,14,.20),0 3px 6px rgba(0,0,0,.11);
}
.ember-stage.nocturne-theme .artist-glass-room .stage-overview-panel,
.ember-stage.nocturne-theme .artist-glass-room .editorial-card { background-color: rgba(10,14,17,.44); }
.ember-stage.mirrorball-theme .artist-glass-room .stage-overview-panel,
.ember-stage.mirrorball-theme .artist-glass-room .editorial-card { background-color: rgba(15,21,30,.29); }
.ember-stage.christmas-theme .artist-glass-room .stage-overview-panel,
.ember-stage.christmas-theme .artist-glass-room .editorial-card { background-color: rgba(12,30,24,.37); }

.ember-stage .artist-glass-room .artist-glass-selector {
 background-color: rgba(10,17,20,.26);
 background-image: linear-gradient(115deg,rgba(255,222,179,.055),rgba(255,255,255,0) 39%,rgba(183,220,241,.035) 82%,rgba(234,202,230,.055));
 box-shadow: inset 0 1px 1px rgba(255,245,220,.23),inset 1px 0 rgba(196,226,239,.12),inset -1px -1px rgba(190,205,227,.09),0 2px 4px rgba(0,0,0,.15);
}
.ember-stage .artist-glass-room .artist-glass-selector button.stage-tab {
 background-color: transparent; background-image: none; border: none;
 color: #c6c1b2; box-shadow: none;
 transition-property: background-color,box-shadow,color;
 transition-duration: 180ms; transition-timing-function: ease-out;
 outline-width: 0; outline-style: none;
}
.ember-stage .artist-glass-room .artist-glass-selector button.stage-tab:checked {
 background-color: rgba(194,219,223,.065);
 background-image: linear-gradient(124deg,rgba(255,236,191,.09),rgba(248,249,239,0) 42%,rgba(179,219,238,.025) 76%,rgba(236,204,231,.06));
 color: #fff0cd;
 box-shadow: inset 0 1px rgba(255,242,209,.31),inset 1px 0 rgba(189,225,242,.22),inset -1px -1px rgba(227,212,237,.13),0 2px 3px rgba(0,0,0,.13);
}
.ember-stage .artist-glass-room .artist-glass-selector button.stage-tab:hover,
.ember-stage .artist-glass-room .artist-glass-selector button.stage-tab:focus {
 color: #fff0cf; background-color: rgba(228,228,213,.045);
 box-shadow: inset 0 0 0 1px rgba(239,220,179,.19);
}
.ember-stage .artist-glass-room .artist-glass-selector button.stage-tab:active {
 background-color: rgba(12,17,18,.20);
 box-shadow: inset 0 2px 4px rgba(0,0,0,.25),inset 0 -1px rgba(236,224,203,.10);
}

.ember-stage .artist-glass-room button.stage-quiet {
 background-color: rgba(17,26,28,.12);
 background-image: linear-gradient(118deg,rgba(248,224,191,.065),rgba(255,249,229,0) 39%,rgba(183,224,240,.022) 76%,rgba(234,204,233,.055)),
                   linear-gradient(to bottom,rgba(255,247,225,.085),rgba(255,247,225,0) 27%,rgba(208,222,238,0) 79%,rgba(208,222,238,.035));
 border-color: rgba(214,228,226,.14); border-top-color: rgba(255,240,205,.30);
 border-left-color: rgba(191,226,239,.21); border-bottom-color: rgba(197,206,226,.12);
 color: #e2dac7;
 box-shadow: inset 0 1px 1px rgba(255,248,223,.065),0 2px 4px rgba(0,0,0,.18);
 transition-property: background-color,border-color,box-shadow,color;
 transition-duration: 180ms; transition-timing-function: ease-out;
 outline-width: 0; outline-style: none;
}
.ember-stage .artist-glass-room button.stage-quiet:hover,
.ember-stage .artist-glass-room button.stage-quiet:focus {
 background-color: rgba(206,218,213,.07); color: #fff1ce;
 border-top-color: rgba(255,241,201,.43); border-left-color: rgba(194,231,243,.30);
 box-shadow: inset 0 1px 2px rgba(255,244,210,.09),0 3px 6px rgba(0,0,0,.18);
}
.ember-stage .artist-glass-room button.stage-quiet:active {
 background-color: rgba(9,16,19,.20);
 box-shadow: inset 1px 2px 4px rgba(0,0,0,.27),inset 0 -1px rgba(236,221,191,.12);
}
.ember-stage .artist-glass-room button.artist-play-key {
 background-color: #c39a54;
 background-image: linear-gradient(114deg,rgba(255,248,210,.20),rgba(255,240,193,0) 42%,rgba(99,66,23,.13)),
                   linear-gradient(to bottom,#efd599,#d5b26b 47%,#b78d48);
 color: #292b25;
 box-shadow: inset 0 1px rgba(255,246,212,.78),inset 0 -2px rgba(103,71,28,.32),inset 1px 0 rgba(255,237,189,.22),0 3px 5px rgba(0,0,0,.25);
 transition-property: background-color,box-shadow;
 transition-duration: 180ms; transition-timing-function: ease-out;
 outline-width: 0; outline-style: none;
}
.ember-stage .artist-glass-room button.artist-play-key:hover,
.ember-stage .artist-glass-room button.artist-play-key:focus {
 box-shadow: inset 0 1px rgba(255,250,221,.9),inset 0 -2px rgba(103,71,28,.28),0 2px 6px rgba(0,0,0,.22),0 0 5px rgba(235,191,103,.10);
}
.ember-stage .artist-glass-room button.artist-play-key:active {
 box-shadow: inset 0 2px 5px rgba(82,53,20,.35),inset 0 -1px rgba(255,238,194,.32),0 1px 2px rgba(0,0,0,.15);
}
.ember-stage .artist-glass-room button.artist-play-key:disabled {
 background-image: linear-gradient(to bottom,#81765c,#595440); color: #c6bea8;
 box-shadow: inset 0 1px rgba(225,215,188,.12),inset 0 -1px rgba(0,0,0,.18);
}

.ember-stage .artist-glass-room .stage-artist-chip {
 background-color: rgba(7,14,16,.25);
 background-image: linear-gradient(to bottom,rgba(2,6,8,.13),rgba(245,230,198,.025));
 border-color: rgba(221,222,207,.10); color: #d5c39f;
 box-shadow: inset 0 1px 2px rgba(0,0,0,.13),0 1px rgba(255,241,207,.045);
}
.ember-stage .artist-glass-room .stage-overview-panel .stage-track-row {
 background-color: rgba(7,13,18,.19);
 background-image: linear-gradient(to bottom,rgba(1,5,7,.08),rgba(221,231,224,.012));
 box-shadow: inset 0 1px 2px rgba(0,0,0,.14),inset 0 -1px rgba(243,234,206,.035);
}
.ember-stage .artist-glass-room .stage-overview-panel button.stage-add {
 background-color: rgba(30,41,40,.26);
 background-image: linear-gradient(125deg,rgba(255,238,199,.075),rgba(244,247,234,0) 42%,rgba(188,222,241,.03));
 color: #e7d2a6;
 box-shadow: inset 0 1px rgba(255,243,207,.17),inset 0 -1px rgba(0,0,0,.24),0 1px 3px rgba(0,0,0,.18);
 transition-property: background-color,box-shadow,color; transition-duration: 160ms;
}
.ember-stage .artist-glass-room .stage-overview-panel button.stage-add:hover {
 background-color: rgba(214,184,122,.09); color: #ffdc98;
 box-shadow: inset 0 1px rgba(255,238,190,.26),0 2px 4px rgba(0,0,0,.18);
}
.ember-stage .artist-glass-room .stage-overview-panel button.stage-add:active {
 box-shadow: inset 0 2px 3px rgba(0,0,0,.30),inset 0 -1px rgba(255,235,193,.09);
}
.ember-stage .artist-glass-room button.stage-album {
 background-color: rgba(15,23,25,.22);
 background-image: linear-gradient(116deg,rgba(245,222,184,.055),rgba(255,251,235,0) 36%,rgba(177,219,239,.025) 80%,rgba(234,208,233,.035));
 border-color: rgba(211,225,226,.095); border-top-color: rgba(247,234,204,.20);
 box-shadow: inset 0 1px rgba(255,245,215,.035),0 2px 4px rgba(0,0,0,.11);
 transition-property: background-color,border-color,box-shadow; transition-duration: 180ms;
}
.ember-stage .artist-glass-room button.stage-album:hover,
.ember-stage .artist-glass-room button.stage-album:focus {
 background-color: rgba(204,217,210,.04); border-top-color: rgba(255,234,187,.35);
 border-color: rgba(230,211,171,.22); box-shadow: inset 0 1px rgba(255,245,215,.06),0 3px 6px rgba(0,0,0,.16);
}
.ember-stage .artist-glass-room button.stage-album:active { box-shadow: inset 0 2px 5px rgba(0,0,0,.24); }
.ember-stage .artist-glass-room .stage-feature-title,
.ember-stage .artist-glass-room .stage-artist-section,
.ember-stage .artist-glass-room .stage-card-title,
.ember-stage .artist-glass-room .stage-card-title label { color: #f0e7d3; }
.ember-stage .artist-glass-room .stage-feature-caption,
.ember-stage .artist-glass-room .stage-card-subtitle,
.ember-stage .artist-glass-room .stage-overview-story { color: #bfb8a7; }
.ember-stage .artist-glass-room .stage-feature-action { color: #e6c588; }
.ember-stage .artist-glass-room .stage-artist-kicker { color: #ceb581; }
.ember-stage .artist-glass-room button.stage-quiet:disabled,
.ember-stage .artist-glass-room .stage-overview-panel button.stage-add:disabled {
 background-image: none; background-color: rgba(12,18,20,.07); color: #858777;
 box-shadow: inset 0 1px rgba(221,225,209,.025);
}
'''
