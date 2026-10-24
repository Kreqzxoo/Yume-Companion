# NOTICE

**Yume Companion** is a modified version of **Soul of Waifu** (v2.5.x)

- Original work: Soul of Waifu — Copyright (C) jofizcd — https://github.com/jofizcd/Soul-of-Waifu
- Licence of the original and of this project: **GNU General Public License v3.0** (see `LICENSE`)

This is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the
Free Software Foundation, version 3. It is distributed WITHOUT ANY WARRANTY.

Yume Companion is **not** the official Soul of Waifu and is not affiliated with or endorsed by its author.

## Changes compared to the original (GPL-3.0 §5a)

Modified in 2026 (summary, not complete):

- Android connector: pairing by QR code, per-device tokens, phone control channel, speech input / output for the phone app,
  character list / history / sync / avatar / VRM model endpoints, "plain text" and "spoken words only" modes
- Native Android app "Yume Companion" (`android/`) with chat, calls, wake word, local 3D avatar,
  offline emergency mode, alarm clock, Spotify control, video call, call protection, car and wall modes
- Memory and companion system: Soul Memory pipeline / topic search, hormone model, startup greeting
- Organizer: calendar (ICS), mail (read-only), reminders, lists, routines, commute, people and trips, knowledge base,
  documents, skills, jobs, inbox ("Share to Yume"), mood awareness, weekly report, presence
- Voice: Qwen3-TTS device handling, shared speech cleaner, wake-word answers rendered by the PC, speech recognition filters,
  WebRTC AEC3 echo cancellation, "Hey Yume" on the PC
- Performance dashboard, tool log, self test, automatic profile backups (`.yumepack`), update check against a configurable repository
- Yume LLM Server (`llm-server/`): turns another PC into an AI server (language, vision, image, tool models)
- New visual design ("Yume look": navigation, icon set, cards, colours, texts), own names for the original's sections, links to the original project removed from the program (the original author stays credited in this file, in the About dialog and in `LICENSE`)
- Image generation robustness, updater / build tools (`updater/`), rebranding support (`rebrand/`), German translation, many fixes (see git history)

## Third-party components

See `docs/LIZENZEN_UND_UPLOAD.md` for the list of components, their licences and what must not be uploaded.
The sample characters (Yume, Mika, Kai), their expression images and the screenshots in `docs/images` were created for this project
with fictional data and may be used under the same licence as the project.
