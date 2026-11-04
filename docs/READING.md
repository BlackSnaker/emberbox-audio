# Stories behind the music

**English** · [Русский](READING.ru.md)

Open **About** in an artist room, or **About this album** on a release.
Editorial prose appears on a warm matte surface, with a comfortable reading
width, a larger opening paragraph, a serif heading and generous spacing.
The shared page gently brings the article into view. Manual scrolling cancels
that movement immediately; playback controls remain available.

Choose **Translate to Russian**. The original remains visible while a small
amber progress line indicates preparation. The finished translation crossfades
into place. **Show original** and **Read in Russian** switch versions without
another request. Both versions support selection and copying.

Source-supplied Russian text needs no extra translation. Missing descriptions
remain explicit: Ember does not invent biographies or reviews. The reader works
with descriptions supplied by Apple Music, Spotify and Yandex Music.

## Translation and data

Google Translate receives **only the public description text**, after an explicit
button press. No passwords, cookies, tokens, library or listening history are
attached. HTTPS POST keeps prose out of request URLs. Simply opening a page
does not contact the translator.

This is automatic translation; names, musical terms and idioms can benefit from
comparison with the original. Attribution identifies the translator. The
connection uses Google Translate's public web service, **not the authenticated
Cloud Translation API**. It requires no separate key, but service availability
and limits can change. Network errors, rate limits and incomplete replies retain
the original with a retry action. Partial translations are never labelled complete.

The exact source text keys a local cache of up to 64 translations for 30 days.
Changed descriptions cannot inherit an older text's translation. The cache stays
in the user's application directory, is never published to GitHub and permits
offline reuse of saved translations. Language choices persist within the current
player session.

## Motion and performance

A single dedicated worker processes a bounded queue independently of playback.
Long descriptions retain paragraph/sentence context and all source characters;
concurrent identical requests share one job. Closed readers discard late replies.

Entrance and language changes use finite transitions. The larger text layout is
reserved before a crossfade, avoiding per-frame paragraph reflow. System reduced
motion settings are respected, and animation callbacks stop after transitions.
No local translation model is loaded.
