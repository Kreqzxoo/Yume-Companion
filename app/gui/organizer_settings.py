"""Settings page 'Organizer': calendar links (ICS), mail (IMAP, read-only), reminders and own appointments."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("OrganizerSettings")

BTN_STYLE = ("QPushButton { background: rgba(255,255,255,0.045); color:#e0e0e0; border:1px solid rgba(255,255,255,0.13); "
             "border-radius:8px; padding:4px 12px; } QPushButton:hover { background: rgba(255,143,199,0.14); "
             "border-color: rgba(255,143,199,0.5); } QPushButton:disabled { color: rgba(255,255,255,0.3); }")
NOTE_STYLE = "color: rgba(220, 220, 230, 0.78); border: none; background: transparent;"


def _label(text, style=NOTE_STYLE):
    w = QtWidgets.QLabel(text)
    w.setWordWrap(True)
    w.setStyleSheet(style)
    return w


def build_organizer_page(ui, create_scroll_page, create_glass_card, font_input):
    tr = ui.translations.get
    page, layout = create_scroll_page()
    page.setObjectName("organizer_tab")

    def button(text):
        b = QtWidgets.QPushButton(text)
        b.setFont(font_input)
        b.setFixedHeight(38)
        b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(BTN_STYLE)
        return b

    # ---------------- calendar
    card, l = create_glass_card(tr("organizer_cal_title", "Calendar"))
    l.addWidget(_label(tr(
        "organizer_cal_intro",
        "Yume reads your calendars and can add own appointments (\"Yume, trag morgen um 15 Uhr Zahnarzt ein\"). The phone's own calendar is read through "
        "the phone automatically (calendar permission in the app). For Google / Outlook / Apple calendars on the PC paste the secret iCal link here, "
        "one per line (Google: Calendar settings > your calendar > \"Secret address in iCal format\"). These links are read-only and stored encrypted.")))
    ui.plainTextEdit_organizer_ics = QtWidgets.QPlainTextEdit()
    ui.plainTextEdit_organizer_ics.setFixedHeight(86)
    ui.plainTextEdit_organizer_ics.setFont(font_input)
    ui.plainTextEdit_organizer_ics.setPlaceholderText("https://calendar.google.com/calendar/ical/.../basic.ics")
    l.addWidget(ui.plainTextEdit_organizer_ics)
    ui.pushButton_organizer_ics = button(tr("organizer_save_test", "Save and test"))
    l.addWidget(ui.pushButton_organizer_ics)
    ui.label_organizer_ics = _label("", "color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.label_organizer_ics)
    layout.addWidget(card)

    # ---------------- mail
    mcard, ml = create_glass_card(tr("organizer_mail_title", "Mail (read-only)"))
    ml.addWidget(_label(tr(
        "organizer_mail_intro",
        "Yume can tell you about new mails and summarise them. It only READS (nothing is sent, deleted or marked as read). Use an IMAP app password, "
        "not your normal password (Gmail: Google account > Security > App passwords; IMAP must be on). The password is stored encrypted. "
        "Note: the text of mails Yume reads is sent to the language model you chose - with a cloud model that means to that provider.")))
    form = QtWidgets.QFormLayout()
    form.setHorizontalSpacing(22)

    def line(placeholder="", password=False):
        e = QtWidgets.QLineEdit()
        e.setFixedHeight(38)
        e.setFont(font_input)
        e.setPlaceholderText(placeholder)
        if password:
            e.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        return e
    ui.lineEdit_mail_host = line("imap.gmail.com")
    ui.lineEdit_mail_port = line("993")
    ui.lineEdit_mail_user = line("name@example.com")
    ui.lineEdit_mail_password = line("", True)
    ui.lineEdit_mail_folder = line("INBOX")
    form.addRow(tr("organizer_mail_host", "IMAP server"), ui.lineEdit_mail_host)
    form.addRow(tr("organizer_mail_port", "Port"), ui.lineEdit_mail_port)
    form.addRow(tr("organizer_mail_user", "Address / user"), ui.lineEdit_mail_user)
    form.addRow(tr("organizer_mail_password", "App password"), ui.lineEdit_mail_password)
    form.addRow(tr("organizer_mail_folder", "Folder"), ui.lineEdit_mail_folder)
    ml.addLayout(form)
    mrow = QtWidgets.QHBoxLayout()
    ui.pushButton_mail_save = button(tr("organizer_save_test", "Save and test"))
    ui.pushButton_mail_remove = button(tr("organizer_mail_remove", "Remove mail account"))
    mrow.addWidget(ui.pushButton_mail_save)
    mrow.addWidget(ui.pushButton_mail_remove)
    ml.addLayout(mrow)
    ui.label_mail_status = _label("", "color: #B9A9C9; border: none; background: transparent;")
    ml.addWidget(ui.label_mail_status)
    layout.addWidget(mcard)

    # ---------------- reminders and own appointments
    rcard, rl = create_glass_card(tr("organizer_rem_title", "Reminders and own appointments"))
    rl.addWidget(_label(tr(
        "organizer_rem_intro",
        "Ask Yume: \"erinnere mich in 20 Minuten an die Wäsche\". At the time a message appears here and as a notification on the paired phone "
        "(the program must be running). Open items:")))
    ui.listWidget_organizer = QtWidgets.QListWidget()
    ui.listWidget_organizer.setMinimumHeight(170)
    ui.listWidget_organizer.setFont(font_input)
    rl.addWidget(ui.listWidget_organizer)
    rrow = QtWidgets.QHBoxLayout()
    ui.pushButton_organizer_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_organizer_delete = button(tr("organizer_delete", "Delete selected"))
    rrow.addWidget(ui.pushButton_organizer_refresh)
    rrow.addWidget(ui.pushButton_organizer_delete)
    rl.addLayout(rrow)
    layout.addWidget(rcard)

    # ---------------- lists
    lc, ll = create_glass_card(tr("lists_title", "Lists (shopping, to-do ...)"))
    ll.addWidget(_label(tr("lists_intro", "Say \"Setz Milch auf die Einkaufsliste\" or \"Was muss ich noch kaufen?\". The lists work in the PC and the phone chat.")))
    ui.listWidget_lists = QtWidgets.QListWidget()
    ui.listWidget_lists.setMinimumHeight(130)
    ui.listWidget_lists.setFont(font_input)
    ll.addWidget(ui.listWidget_lists)
    lrow2 = QtWidgets.QHBoxLayout()
    ui.pushButton_lists_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_lists_delete = button(tr("organizer_delete", "Delete selected"))
    lrow2.addWidget(ui.pushButton_lists_refresh)
    lrow2.addWidget(ui.pushButton_lists_delete)
    ll.addLayout(lrow2)
    layout.addWidget(lc)

    # ---------------- activity log with undo
    ac, al = create_glass_card(tr("activity_title", "What Yume did today"))
    al.addWidget(_label(tr("activity_intro", "Every action Yume carried out (music, reminders, appointments, lists ...). Entries with a back arrow can be taken back. You can also say \"Mach das rückgängig\".")))
    ui.listWidget_activity = QtWidgets.QListWidget()
    ui.listWidget_activity.setMinimumHeight(190)
    ui.listWidget_activity.setFont(font_input)
    al.addWidget(ui.listWidget_activity)
    arow = QtWidgets.QHBoxLayout()
    ui.pushButton_activity_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_activity_undo = button(tr("activity_undo", "Undo selected"))
    arow.addWidget(ui.pushButton_activity_refresh)
    arow.addWidget(ui.pushButton_activity_undo)
    al.addLayout(arow)
    ui.label_activity = _label("", "color: #B9A9C9; border: none; background: transparent;")
    al.addWidget(ui.label_activity)
    layout.addWidget(ac)

    # ---------------- routines
    cc, cl = create_glass_card(tr("routine_title", "Routines"))
    cl.addWidget(_label(tr(
        "routine_intro",
        "Morning briefing: at the set time Yume tells you the weather, today's appointments, reminders and new mails (on the phone when it is connected, "
        "otherwise on the PC; the program must be running). Say \"Guten Morgen\" or \"Briefing\" any time to get it at once. "
        "Good night: say \"Gute Nacht\" and Yume pauses the music, switches the flashlight off, checks your alarm and tells you what is up tomorrow.")))
    frow = QtWidgets.QFormLayout()
    frow.setHorizontalSpacing(22)
    ui.lineEdit_routine_location = QtWidgets.QLineEdit()
    ui.lineEdit_routine_location.setFixedHeight(38)
    ui.lineEdit_routine_location.setFont(font_input)
    ui.lineEdit_routine_location.setPlaceholderText("z.B. Hamburg")
    frow.addRow(tr("routine_location", "Place for the weather"), ui.lineEdit_routine_location)
    cl.addLayout(frow)
    lrow = QtWidgets.QHBoxLayout()
    ui.pushButton_routine_weather = button(tr("routine_weather_test", "Save place and test weather"))
    lrow.addWidget(ui.pushButton_routine_weather)
    cl.addLayout(lrow)
    ui.label_routine_weather = _label("", "color: #B9A9C9; border: none; background: transparent;")
    cl.addWidget(ui.label_routine_weather)

    ui.checkBox_routine_morning = QtWidgets.QCheckBox(tr("routine_morning_on", "Give me the morning briefing automatically"))
    ui.checkBox_routine_morning.setFont(font_input)
    cl.addWidget(ui.checkBox_routine_morning)
    trow = QtWidgets.QHBoxLayout()
    trow.addWidget(_label(tr("routine_time", "Time:")))
    ui.timeEdit_routine = QtWidgets.QTimeEdit(QtCore.QTime(7, 30))
    ui.timeEdit_routine.setDisplayFormat("HH:mm")
    ui.timeEdit_routine.setFixedHeight(34)
    ui.timeEdit_routine.setFixedWidth(90)
    ui.timeEdit_routine.setFont(font_input)
    ui.timeEdit_routine.setStyleSheet("QTimeEdit { color: #ffffff; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.18); border-radius: 6px; padding: 2px 6px; }")
    trow.addWidget(ui.timeEdit_routine)
    ui.checkBox_routine_days = []
    for i, name in enumerate(("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")):
        cb = QtWidgets.QCheckBox(name)
        cb.setFont(font_input)
        ui.checkBox_routine_days.append(cb)
        trow.addWidget(cb)
    trow.addStretch()
    cl.addLayout(trow)
    irow = QtWidgets.QHBoxLayout()
    ui.checkBox_routine_inc = {}
    for key, text in (("weather", tr("routine_inc_weather", "Weather")), ("calendar", tr("routine_inc_calendar", "Appointments")),
                      ("reminders", tr("routine_inc_reminders", "Reminders")), ("mail", tr("routine_inc_mail", "New mails"))):
        cb = QtWidgets.QCheckBox(text)
        cb.setFont(font_input)
        ui.checkBox_routine_inc[key] = cb
        irow.addWidget(cb)
    irow.addStretch()
    cl.addLayout(irow)
    orow = QtWidgets.QHBoxLayout()
    orow.addWidget(_label(tr("routine_output", "Spoken on:")))
    ui.comboBox_routine_output = QtWidgets.QComboBox()
    ui.comboBox_routine_output.setFont(font_input)
    ui.comboBox_routine_output.setMinimumWidth(300)
    for value, text in (("auto", tr("routine_out_auto", "Phone if connected, otherwise PC")), ("phone", tr("routine_out_phone", "Phone")), ("pc", tr("routine_out_pc", "PC"))):
        ui.comboBox_routine_output.addItem(text, value)
    orow.addWidget(ui.comboBox_routine_output)
    orow.addStretch()
    cl.addLayout(orow)
    cl.addWidget(_label(tr("commute_title", "Punctuality assistant: when do I have to leave?"), "color: #ffffff; border: none; background: transparent; font-weight: bold;"))
    cform = QtWidgets.QFormLayout()
    cform.setHorizontalSpacing(22)
    ui.lineEdit_commute_home = QtWidgets.QLineEdit()
    ui.lineEdit_commute_home.setFixedHeight(38)
    ui.lineEdit_commute_home.setFont(font_input)
    ui.lineEdit_commute_home.setPlaceholderText("Musterstraße 1, 20095 Hamburg")
    cform.addRow(tr("commute_home", "Home address"), ui.lineEdit_commute_home)
    ui.comboBox_commute_mode = QtWidgets.QComboBox()
    ui.comboBox_commute_mode.setFont(font_input)
    for value, text in (("car", tr("commute_car", "Car")), ("bike", tr("commute_bike", "Bike")), ("foot", tr("commute_foot", "On foot"))):
        ui.comboBox_commute_mode.addItem(text, value)
    cform.addRow(tr("commute_mode", "Travel by"), ui.comboBox_commute_mode)
    ui.spinBox_commute_buffer = QtWidgets.QSpinBox()
    ui.spinBox_commute_buffer.setRange(0, 60)
    ui.spinBox_commute_buffer.setSuffix(" min")
    ui.spinBox_commute_buffer.setFont(font_input)
    cform.addRow(tr("commute_buffer", "Buffer"), ui.spinBox_commute_buffer)
    cl.addLayout(cform)
    ui.checkBox_rain_alert = QtWidgets.QCheckBox(tr("rain_alert", "Rain alert on the phone when I am out and rain is about to start (needs the phone's location)"))
    ui.checkBox_rain_alert.setFont(font_input)
    cl.addWidget(ui.checkBox_rain_alert)
    ui.checkBox_commute_on = QtWidgets.QCheckBox(tr("commute_on", "Tell me when it is time to leave (appointments with a place)"))
    ui.checkBox_commute_on.setFont(font_input)
    cl.addWidget(ui.checkBox_commute_on)
    ui.checkBox_report = QtWidgets.QCheckBox(tr("report_on", "Weekly review every Sunday at 18:00 (what I did, how you were doing, what is coming up)"))
    ui.checkBox_report.setFont(font_input)
    cl.addWidget(ui.checkBox_report)
    ui.label_mood = _label("", "color: #B9A9C9; border: none; background: transparent;")
    cl.addWidget(ui.label_mood)
    ui.checkBox_presence = QtWidgets.QCheckBox(tr("presence_on", "Presence: notice when I leave / come home (phone connected from the home network) and run my sentences"))
    ui.checkBox_presence.setFont(font_input)
    cl.addWidget(ui.checkBox_presence)
    ui.presence_fields = {}
    for key, label in (("on_leave", tr("presence_leave", "When I leave (a phone is away)")), ("on_all_left", tr("presence_all", "When everybody is gone")),
                       ("on_arrive", tr("presence_arrive", "When someone arrives")), ("on_first_arrived", tr("presence_first", "When the first one arrives"))):
        cl.addWidget(_label(label))
        e = QtWidgets.QLineEdit()
        e.setFixedHeight(34)
        e.setFont(font_input)
        e.setPlaceholderText(tr("presence_ph", "e.g. Mach das Licht aus; pausiere die Musik   (several steps with ;)"))
        ui.presence_fields[key] = e
        cl.addWidget(e)
    ui.checkBox_routine_greet = QtWidgets.QCheckBox(tr("routine_greet", "\"Guten Morgen\" / \"Briefing\" / \"Gute Nacht\" start the routines"))
    ui.checkBox_routine_greet.setFont(font_input)
    cl.addWidget(ui.checkBox_routine_greet)
    cl.addWidget(_label(tr("routine_night_title", "Good night does:"), "color: #ffffff; border: none; background: transparent; font-weight: bold;"))
    nrow = QtWidgets.QGridLayout()
    ui.checkBox_routine_night = {}
    for key, text in (("pause_music", tr("routine_n_music", "Pause music")), ("flashlight_off", tr("routine_n_light", "Flashlight off")),
                      ("alarms", tr("routine_n_alarm", "Check alarm")), ("tomorrow", tr("routine_n_tomorrow", "Tomorrow's appointments")),
                      ("weather_tomorrow", tr("routine_n_weather", "Weather tomorrow"))):
        cb = QtWidgets.QCheckBox(text)
        cb.setFont(font_input)
        ui.checkBox_routine_night[key] = cb
        nrow.addWidget(cb, (len(ui.checkBox_routine_night) - 1) // 3, (len(ui.checkBox_routine_night) - 1) % 3)
    cl.addLayout(nrow)
    brow = QtWidgets.QHBoxLayout()
    ui.pushButton_routine_test_morning = button(tr("routine_test_morning", "Try morning briefing now"))
    ui.pushButton_routine_test_night = button(tr("routine_test_night", "Try good night now"))
    brow.addWidget(ui.pushButton_routine_test_morning)
    brow.addWidget(ui.pushButton_routine_test_night)
    cl.addLayout(brow)
    layout.addWidget(cc)

    # ---------------- memory + AI behaviour
    kc, kl = create_glass_card(tr("memory_title", "What Yume remembers"))
    kl.addWidget(_label(tr(
        "memory_intro",
        "Say \"Merk dir, dass ich morgens keine Regenhinweise mag\" and Yume keeps it for good and uses it in every chat, briefing and routine. "
        "Here you can see and delete what she remembers.")))
    ui.listWidget_memory = QtWidgets.QListWidget()
    ui.listWidget_memory.setMinimumHeight(130)
    ui.listWidget_memory.setFont(font_input)
    kl.addWidget(ui.listWidget_memory)
    krow = QtWidgets.QHBoxLayout()
    ui.pushButton_memory_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_memory_delete = button(tr("organizer_delete", "Delete selected"))
    krow.addWidget(ui.pushButton_memory_refresh)
    krow.addWidget(ui.pushButton_memory_delete)
    kl.addLayout(krow)
    ui.pushButton_selftest = button(tr("selftest_run", "Run self test"))
    kl.addWidget(ui.pushButton_selftest)
    ui.label_selftest = _label("", "color: #B9A9C9; border: none; background: transparent;")
    ui.label_selftest.setTextFormat(QtCore.Qt.TextFormat.RichText)
    kl.addWidget(ui.label_selftest)
    ui.checkBox_mood_aware = QtWidgets.QCheckBox(tr("mood_aware", "Mood awareness: Yume notices tiredness, stress or sadness in your words and answers accordingly"))
    ui.checkBox_mood_aware.setFont(font_input)
    kl.addWidget(ui.checkBox_mood_aware)
    ui.checkBox_voice_mood = QtWidgets.QCheckBox(tr("voice_mood", "Voice awareness (experimental): Yume estimates from the sound and tempo of your voice how you are (only numbers, no recording is stored)"))
    ui.checkBox_voice_mood.setFont(font_input)
    kl.addWidget(ui.checkBox_voice_mood)
    ui.checkBox_llm_thinking = QtWidgets.QCheckBox(tr("llm_thinking", "Thinking mode of the language model (slower, better for hard questions)"))
    ui.checkBox_llm_thinking.setFont(font_input)
    kl.addWidget(ui.checkBox_llm_thinking)
    kl.addWidget(_label(tr("llm_thinking_note", "Off (recommended): faster answers and reliable tool calls. Applies to models like Qwen3 on your own server.")))
    layout.addWidget(kc)

    # ---------------- journal
    jc, jl = create_glass_card(tr("journal_title", "Journal"))
    jl.addWidget(_label(tr("journal_intro", "Tell Yume about your day (\"Schreib ins Tagebuch: ...\" or just talk in the evening). Entries of the last weeks:")))
    ui.listWidget_journal = QtWidgets.QListWidget()
    ui.listWidget_journal.setMinimumHeight(150)
    ui.listWidget_journal.setFont(font_input)
    jl.addWidget(ui.listWidget_journal)
    jrow = QtWidgets.QHBoxLayout()
    ui.pushButton_journal_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_journal_delete = button(tr("organizer_delete", "Delete selected"))
    jrow.addWidget(ui.pushButton_journal_refresh)
    jrow.addWidget(ui.pushButton_journal_delete)
    jl.addLayout(jrow)
    layout.addWidget(jc)

    # ---------------- knowledge base
    wc, wl = create_glass_card(tr("kb_title", "Knowledge base (your documents)"))
    wl.addWidget(_label(tr("kb_intro", "Choose folders with your PDFs, Word files and notes. Yume reads them once (locally, nothing leaves the PC) and can then answer "
                                        "\"What does my rental contract say about notice periods?\" with file name and page. New and changed files are picked up automatically.")))
    ui.listWidget_kb = QtWidgets.QListWidget()
    ui.listWidget_kb.setMinimumHeight(100)
    ui.listWidget_kb.setFont(font_input)
    wl.addWidget(ui.listWidget_kb)
    wrow = QtWidgets.QHBoxLayout()
    ui.pushButton_kb_add = button(tr("kb_add", "Add folder ..."))
    ui.pushButton_kb_remove = button(tr("kb_remove", "Remove selected"))
    ui.pushButton_kb_index = button(tr("kb_index", "Read documents now"))
    wrow.addWidget(ui.pushButton_kb_add)
    wrow.addWidget(ui.pushButton_kb_remove)
    wrow.addWidget(ui.pushButton_kb_index)
    wl.addLayout(wrow)
    ui.checkBox_kb_semantic = QtWidgets.QCheckBox(tr("kb_semantic", "Meaning-based search (also finds passages without matching words; downloads a model once, about 470 MB)"))
    ui.checkBox_kb_semantic.setFont(font_input)
    wl.addWidget(ui.checkBox_kb_semantic)
    ui.label_kb = _label("", "color: #B9A9C9; border: none; background: transparent;")
    wl.addWidget(ui.label_kb)
    layout.addWidget(wc)

    # ---------------- jobs, routines, skills
    sc, sl = create_glass_card(tr("auto_title", "Background jobs, routines and skills"))
    sl.addWidget(_label(tr("auto_intro", "Jobs: tasks Yume works on by herself. Routines: sequences you taught her by voice (\"Merk dir das als Ablauf Feierabend ...\"). Skills: small programs "
                                          "Yume wrote for herself after you approved the code.")))
    ui.listWidget_auto = QtWidgets.QListWidget()
    ui.listWidget_auto.setMinimumHeight(170)
    ui.listWidget_auto.setFont(font_input)
    sl.addWidget(ui.listWidget_auto)
    srow = QtWidgets.QHBoxLayout()
    ui.pushButton_auto_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_auto_delete = button(tr("organizer_delete", "Delete selected"))
    ui.pushButton_auto_folder = button(tr("auto_folder", "Open skills folder"))
    srow.addWidget(ui.pushButton_auto_refresh)
    srow.addWidget(ui.pushButton_auto_delete)
    srow.addWidget(ui.pushButton_auto_folder)
    sl.addLayout(srow)
    ui.label_auto = _label("", "color: #B9A9C9; border: none; background: transparent;")
    sl.addWidget(ui.label_auto)
    layout.addWidget(sc)

    # ---------------- people and trips
    pc2, pl2 = create_glass_card(tr("people_title", "People and trips"))
    pl2.addWidget(_label(tr("people_intro", "Birthdays, notes and gift ideas (\"Anna hat am 12. Mai Geburtstag und mag keine Pilze\") and planned trips. Yume reminds you of birthdays and uses everything in her answers.")))
    ui.listWidget_people = QtWidgets.QListWidget()
    ui.listWidget_people.setMinimumHeight(150)
    ui.listWidget_people.setFont(font_input)
    pl2.addWidget(ui.listWidget_people)
    prow = QtWidgets.QHBoxLayout()
    ui.pushButton_people_refresh = button(tr("organizer_refresh", "Refresh"))
    ui.pushButton_people_delete = button(tr("organizer_delete", "Delete selected"))
    prow.addWidget(ui.pushButton_people_refresh)
    prow.addWidget(ui.pushButton_people_delete)
    pl2.addLayout(prow)
    layout.addWidget(pc2)

    # ---------------- Hey Yume on the PC
    hc, hl = create_glass_card(tr("pcwake_title", "Hey Yume on the PC"))
    hl.addWidget(_label(tr("pcwake_intro", "Yume listens in the background (also with the chat closed) for your wake phrase. When she hears it, a small card with her 3D model appears in the lower "
                                          "right corner, you talk and she answers. Everything is checked on this PC; nothing is stored. Uses the microphone and the speech recognition (Whisper).")))
    ui.checkBox_pcwake_on = QtWidgets.QCheckBox(tr("pcwake_on", "Listen for the wake phrase"))
    ui.checkBox_pcwake_on.setFont(font_input)
    hl.addWidget(ui.checkBox_pcwake_on)
    hform = QtWidgets.QFormLayout()
    hform.setHorizontalSpacing(22)
    ui.lineEdit_pcwake_phrase = QtWidgets.QLineEdit("Hey Yume")
    ui.lineEdit_pcwake_phrase.setFixedHeight(38)
    ui.lineEdit_pcwake_phrase.setFont(font_input)
    hform.addRow(tr("pcwake_phrase", "Wake phrase"), ui.lineEdit_pcwake_phrase)
    ui.spinBox_pcwake_seconds = QtWidgets.QSpinBox()
    ui.spinBox_pcwake_seconds.setRange(8, 120)
    ui.spinBox_pcwake_seconds.setValue(25)
    ui.spinBox_pcwake_seconds.setSuffix(" s")
    ui.spinBox_pcwake_seconds.setFont(font_input)
    hform.addRow(tr("pcwake_seconds", "Stay awake after the last sentence"), ui.spinBox_pcwake_seconds)
    hl.addLayout(hform)
    ui.checkBox_pcwake_vrm = QtWidgets.QCheckBox(tr("pcwake_vrm", "Show the 3D model (VRM) in the card"))
    ui.checkBox_pcwake_vrm.setFont(font_input)
    ui.checkBox_pcwake_chime = QtWidgets.QCheckBox(tr("pcwake_chime", "Play a short sound when she woke up"))
    ui.checkBox_pcwake_chime.setFont(font_input)
    hl.addWidget(ui.checkBox_pcwake_vrm)
    hl.addWidget(ui.checkBox_pcwake_chime)
    ui.pushButton_pcwake_test = button(tr("pcwake_test", "Show the card now (test)"))
    hl.addWidget(ui.pushButton_pcwake_test)
    ui.label_pcwake = _label("", "color: #B9A9C9; border: none; background: transparent;")
    hl.addWidget(ui.label_pcwake)
    layout.addWidget(hc)

    # ---------------- my details for letters and invoices
    mc2, ml2 = create_glass_card(tr("profile_title", "My details (for letters and invoices)"))
    ml2.addWidget(_label(tr("profile_intro", "Yume uses these when she writes letters, invoices and your CV. They stay on this PC. Documents are saved in Documents\\Yume Dokumente.")))
    pform = QtWidgets.QFormLayout()
    pform.setHorizontalSpacing(22)
    ui.profile_fields = {}
    for key, label in (("name", tr("profile_name", "Name")), ("company", tr("profile_company", "Company (optional)")), ("street", tr("profile_street", "Street and number")),
                       ("city", tr("profile_city", "Postal code and city")), ("email", tr("profile_email", "E-mail")), ("phone", tr("profile_phone", "Phone")),
                       ("iban", "IBAN"), ("bic", "BIC"), ("tax_id", tr("profile_tax", "Tax number"))):
        e = QtWidgets.QLineEdit()
        e.setFixedHeight(36)
        e.setFont(font_input)
        ui.profile_fields[key] = e
        pform.addRow(label, e)
    ml2.addLayout(pform)
    ui.checkBox_kleinunternehmer = QtWidgets.QCheckBox(tr("profile_klein", "Small business (no VAT on invoices, section 19 UStG)"))
    ui.checkBox_kleinunternehmer.setFont(font_input)
    ml2.addWidget(ui.checkBox_kleinunternehmer)
    ui.pushButton_profile_folder = button(tr("profile_folder", "Open the documents folder"))
    ml2.addWidget(ui.pushButton_profile_folder)
    layout.addWidget(mc2)

    # ---------------- mail drafts
    dc2, dl2 = create_glass_card(tr("drafts_title", "Mail drafts"))
    dl2.addWidget(_label(tr("drafts_intro", "Yume writes answers as DRAFTS (\"Antworte auf die Mail von Anna und sag zu\"). Nothing is ever sent by her: open the draft in your mail program and press send.")))
    ui.listWidget_drafts = QtWidgets.QListWidget()
    ui.listWidget_drafts.setMinimumHeight(120)
    ui.listWidget_drafts.setFont(font_input)
    dl2.addWidget(ui.listWidget_drafts)
    drow = QtWidgets.QHBoxLayout()
    ui.pushButton_drafts_open = button(tr("drafts_open", "Open in mail program"))
    ui.pushButton_drafts_copy = button(tr("drafts_copy", "Copy text"))
    ui.pushButton_drafts_delete = button(tr("organizer_delete", "Delete selected"))
    drow.addWidget(ui.pushButton_drafts_open)
    drow.addWidget(ui.pushButton_drafts_copy)
    drow.addWidget(ui.pushButton_drafts_delete)
    dl2.addLayout(drow)
    layout.addWidget(dc2)
    layout.addStretch()

    ui.organizer_controller = OrganizerController(ui)
    return page


class OrganizerController(QtCore.QObject):
    result = QtCore.pyqtSignal(str, object)

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.result.connect(self._on_result)
        ui.pushButton_organizer_ics.clicked.connect(self.save_ics)
        ui.pushButton_mail_save.clicked.connect(self.save_mail)
        ui.pushButton_mail_remove.clicked.connect(self.remove_mail)
        ui.pushButton_organizer_refresh.clicked.connect(self.refresh_list)
        ui.pushButton_organizer_delete.clicked.connect(self.delete_selected)
        self.signals = None
        self._loading = True
        self._load_routines()
        self._loading = False
        ui.pushButton_activity_refresh.clicked.connect(self.refresh_activity)
        ui.pushButton_activity_undo.clicked.connect(self.undo_selected)
        self.refresh_activity()
        ui.pushButton_lists_refresh.clicked.connect(self.refresh_lists)
        ui.pushButton_lists_delete.clicked.connect(self.delete_lists)
        self.refresh_lists()
        ui.pushButton_selftest.clicked.connect(self.run_selftest)
        self._loading = True
        self._load_pcwake()
        self._loading = False
        for w in (ui.checkBox_pcwake_on, ui.checkBox_pcwake_vrm, ui.checkBox_pcwake_chime):
            w.toggled.connect(self._save_pcwake)
        ui.lineEdit_pcwake_phrase.editingFinished.connect(self._save_pcwake)
        ui.spinBox_pcwake_seconds.valueChanged.connect(self._save_pcwake)
        ui.pushButton_pcwake_test.clicked.connect(self.test_pcwake)
        self._load_profile()
        ui.pushButton_drafts_open.clicked.connect(self.open_draft)
        ui.pushButton_drafts_copy.clicked.connect(self.copy_draft)
        ui.pushButton_drafts_delete.clicked.connect(self.delete_drafts)
        self.refresh_drafts()
        for e in ui.profile_fields.values():
            e.editingFinished.connect(self._save_profile)
        ui.checkBox_kleinunternehmer.toggled.connect(self._save_profile)
        ui.pushButton_profile_folder.clicked.connect(self.open_documents)
        ui.pushButton_people_refresh.clicked.connect(self.refresh_people)
        ui.pushButton_people_delete.clicked.connect(self.delete_people)
        self.refresh_people()
        ui.pushButton_auto_refresh.clicked.connect(self.refresh_auto)
        ui.pushButton_auto_delete.clicked.connect(self.delete_auto)
        ui.pushButton_auto_folder.clicked.connect(self.open_skills_folder)
        self.refresh_auto()
        ui.checkBox_kb_semantic.toggled.connect(self.kb_semantic)
        ui.pushButton_kb_add.clicked.connect(self.kb_add)
        ui.pushButton_kb_remove.clicked.connect(self.kb_remove)
        ui.pushButton_kb_index.clicked.connect(self.kb_index)
        self.refresh_kb()
        self._kb_timer = QtCore.QTimer(self)
        self._kb_timer.setInterval(1500)
        self._kb_timer.timeout.connect(self._kb_status)
        self._kb_timer.start()
        ui.pushButton_journal_refresh.clicked.connect(self.refresh_journal)
        ui.pushButton_journal_delete.clicked.connect(self.delete_journal)
        self.refresh_journal()
        ui.checkBox_mood_aware.toggled.connect(self._save_mood)
        ui.checkBox_voice_mood.toggled.connect(self._save_voice_mood)
        ui.pushButton_memory_refresh.clicked.connect(self.refresh_memory)
        ui.pushButton_memory_delete.clicked.connect(self.delete_memory)
        self._loading = True
        self._load_ai()
        self._loading = False
        ui.checkBox_llm_thinking.toggled.connect(self._save_ai)
        self.refresh_memory()
        ui.pushButton_routine_weather.clicked.connect(self.test_weather)
        ui.pushButton_routine_test_morning.clicked.connect(lambda: self._test("morning"))
        ui.pushButton_routine_test_night.clicked.connect(lambda: self._test("night"))
        ui.lineEdit_commute_home.editingFinished.connect(self._save_routines)
        ui.spinBox_commute_buffer.valueChanged.connect(self._save_routines)
        ui.comboBox_commute_mode.currentIndexChanged.connect(self._save_routines)
        ui.checkBox_commute_on.toggled.connect(self._save_routines)
        ui.checkBox_rain_alert.toggled.connect(self._save_routines)
        ui.checkBox_report.toggled.connect(self._save_routines)
        ui.checkBox_presence.toggled.connect(self._save_routines)
        for _e in ui.presence_fields.values():
            _e.editingFinished.connect(self._save_routines)
        for w in [ui.checkBox_routine_morning, ui.checkBox_routine_greet, *ui.checkBox_routine_days, *ui.checkBox_routine_inc.values(), *ui.checkBox_routine_night.values()]:
            w.toggled.connect(self._save_routines)
        ui.timeEdit_routine.timeChanged.connect(self._save_routines)
        ui.comboBox_routine_output.currentIndexChanged.connect(self._save_routines)
        self._load_fields()
        self.refresh_list()

    def attach(self, signals):
        self.signals = signals

    def _bg(self, name, fn):
        def run():
            try:
                self.result.emit(name, fn())
            except Exception as exc:
                self.result.emit(name, exc)
        threading.Thread(target=run, daemon=True).start()

    def _load_fields(self):
        from app.utils import organizer
        cfg = organizer.config()
        ui = self.ui
        ui.plainTextEdit_organizer_ics.setPlainText("\n".join(cfg.get("ics", [])))
        im = cfg.get("imap", {})
        ui.lineEdit_mail_host.setText(im.get("host", ""))
        ui.lineEdit_mail_port.setText(str(im.get("port", "") or ""))
        ui.lineEdit_mail_user.setText(im.get("user", ""))
        ui.lineEdit_mail_folder.setText(im.get("folder", ""))
        ui.lineEdit_mail_password.setText("")
        ui.lineEdit_mail_password.setPlaceholderText("(gespeichert)" if im.get("password") else "")

    # ------------------------------------------------------------------ lists
    def refresh_lists(self):
        from app.utils import lists_store
        lw = self.ui.listWidget_lists
        lw.clear()
        for name, items in lists_store.show("").items():
            for it in items:
                item = QtWidgets.QListWidgetItem(f"{name}:  {it['text']}")
                item.setData(QtCore.Qt.ItemDataRole.UserRole, (name, it["id"]))
                lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(alle Listen leer)")

    def delete_lists(self):
        from app.utils import lists_store
        for item in self.ui.listWidget_lists.selectedItems():
            data = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if data:
                lists_store.remove(data[0], data[1])
        self.refresh_lists()

    # ------------------------------------------------------------------ mail drafts
    def refresh_drafts(self):
        from app.utils import organizer
        lw = self.ui.listWidget_drafts
        lw.clear()
        for d in organizer.list_drafts()[:20]:
            item = QtWidgets.QListWidgetItem(f"✉ an {d['to']}: {d['subject']}   ({d['created'][5:].replace('T', ' ')})")
            item.setToolTip(d["body"][:600])
            item.setData(QtCore.Qt.ItemDataRole.UserRole, d["id"])
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(keine Entwürfe)")

    def _selected_draft(self):
        from app.utils import organizer
        items = self.ui.listWidget_drafts.selectedItems()
        key = items[0].data(QtCore.Qt.ItemDataRole.UserRole) if items else "latest"
        return organizer.get_draft(key)

    def open_draft(self):
        from app.utils import organizer
        d = self._selected_draft()
        if d:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(organizer.mailto_url(d)))

    def copy_draft(self):
        d = self._selected_draft()
        if d:
            QtWidgets.QApplication.clipboard().setText(f"An: {d['to']}\nBetreff: {d['subject']}\n\n{d['body']}")

    def delete_drafts(self):
        from app.utils import organizer
        for item in self.ui.listWidget_drafts.selectedItems():
            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if key:
                organizer.delete_draft(key)
        self.refresh_drafts()

    # ------------------------------------------------------------------ my details
    def _load_profile(self):
        from app.utils import documents
        p = documents.profile()
        for key, e in self.ui.profile_fields.items():
            e.setText(str(p.get(key, "")))
        self.ui.checkBox_kleinunternehmer.setChecked(bool(p.get("kleinunternehmer")))

    def _save_profile(self, *_):
        if getattr(self, "_loading", False):
            return
        from app.utils import routines
        cfg = routines.load()
        prof = cfg.setdefault("profile", {})
        for key, e in self.ui.profile_fields.items():
            prof[key] = e.text().strip()
        prof["kleinunternehmer"] = self.ui.checkBox_kleinunternehmer.isChecked()
        routines.save(cfg)

    def open_documents(self):
        from app.utils import documents
        documents.DIR.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(documents.DIR))
        except Exception:
            logger.debug("could not open the documents folder", exc_info=True)

    # ------------------------------------------------------------------ Hey Yume on the PC
    def _load_pcwake(self):
        try:
            s = self._settings()
            ui = self.ui
            ui.checkBox_pcwake_on.setChecked(bool(s.get_main_setting("pcwake_enabled")))
            ui.lineEdit_pcwake_phrase.setText(str(s.get_main_setting("pcwake_phrase") or "Hey Yume"))
            ui.spinBox_pcwake_seconds.setValue(int(s.get_main_setting("pcwake_seconds") or 25))
            vrm = s.get_main_setting("pcwake_vrm")
            ui.checkBox_pcwake_vrm.setChecked(True if vrm is None else bool(vrm))
            chime = s.get_main_setting("pcwake_chime")
            ui.checkBox_pcwake_chime.setChecked(True if chime is None else bool(chime))
        except Exception:
            logger.debug("could not read the Hey Yume settings", exc_info=True)

    def _save_pcwake(self, *_):
        if getattr(self, "_loading", False):
            return
        s = self._settings()
        ui = self.ui
        s.update_main_setting("pcwake_enabled", ui.checkBox_pcwake_on.isChecked())
        s.update_main_setting("pcwake_phrase", ui.lineEdit_pcwake_phrase.text().strip() or "Hey Yume")
        s.update_main_setting("pcwake_seconds", ui.spinBox_pcwake_seconds.value())
        s.update_main_setting("pcwake_vrm", ui.checkBox_pcwake_vrm.isChecked())
        s.update_main_setting("pcwake_chime", ui.checkBox_pcwake_chime.isChecked())
        wake = getattr(self.signals, "pc_wake", None) if self.signals is not None else None
        if wake is None:
            ui.label_pcwake.setText("Gespeichert. Das Zuhören startet beim nächsten Programmstart.")
            return
        if ui.checkBox_pcwake_on.isChecked():
            ui.label_pcwake.setText("Ich höre zu …" if wake.start() else "Das Zuhören konnte nicht gestartet werden (Mikrofon / Spracherkennung, siehe Log).")
        else:
            wake.stop()
            ui.label_pcwake.setText("Zuhören ausgeschaltet.")

    def test_pcwake(self):
        wake = getattr(self.signals, "pc_wake", None) if self.signals is not None else None
        if wake is None:
            self.ui.label_pcwake.setText("Erst nach dem Programmstart verfügbar.")
            return
        wake._show("Ich höre zu …")
        wake.overlay.set_heard("„So sieht die Karte aus.“")
        wake.overlay.hide_later(6000)

    # ------------------------------------------------------------------ people and trips
    def refresh_people(self):
        from app.utils import people, trips
        lw = self.ui.listWidget_people
        lw.clear()
        for p in people.list_people():
            line = f"👤 {p['name']}" + (f" ({p['relation']})" if p.get("relation") else "") + (f" – Geburtstag {people._fmt_birthday(p['birthday'])}" if p.get("birthday") else "")
            item = QtWidgets.QListWidgetItem(line)
            item.setToolTip(people.describe(p))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("person", p["name"]))
            lw.addItem(item)
        for t in trips.list_trips(True):
            item = QtWidgets.QListWidgetItem(f"✈ {t['name']}: {t['destination']}, {t['start']} bis {t['end']}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("trip", t["id"]))
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(noch niemand / keine Reise)")

    def delete_people(self):
        from app.utils import people, trips
        for item in self.ui.listWidget_people.selectedItems():
            data = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if data and data[0] == "person":
                people.remove(data[1])
            elif data and data[0] == "trip":
                trips.remove(data[1])
        self.refresh_people()

    # ------------------------------------------------------------------ jobs / routines / skills
    def refresh_auto(self):
        from app.utils import jobs, macros, skills
        lw = self.ui.listWidget_auto
        lw.clear()
        for j in jobs.list_jobs(15):
            icon = {"queued": "⏳", "running": "⚙", "done": "✓", "failed": "⚠"}.get(j["status"], "•")
            item = QtWidgets.QListWidgetItem(f"{icon} Auftrag: {j['task'][:90]}  ({j['status']})")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("job", j["id"]))
            item.setToolTip(j.get("result", "")[:1500])
            lw.addItem(item)
        for name in macros.names():
            m = macros.get(name)
            item = QtWidgets.QListWidgetItem(f"▶ Ablauf „{name}“: " + " → ".join(m["steps"])[:110])
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("macro", name))
            lw.addItem(item)
        for s in skills.list_skills():
            item = QtWidgets.QListWidgetItem(f"🧩 Fähigkeit {s['name']}: {s['description'][:90]}" + ("" if s["approved"] else "  [nicht freigegeben]"))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("skill", s["name"]))
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(noch nichts)")

    def delete_auto(self):
        from app.utils import jobs, macros, skills
        for item in self.ui.listWidget_auto.selectedItems():
            data = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if not data:
                continue
            if data[0] == "job":
                jobs.cancel(data[1])
            elif data[0] == "macro":
                macros.remove(data[1])
            elif data[0] == "skill":
                skills.delete(data[1])
        self.refresh_auto()

    def open_skills_folder(self):
        from app.utils import skills
        skills.DIR.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(skills.DIR))
        except Exception:
            logger.debug("could not open the skills folder", exc_info=True)

    # ------------------------------------------------------------------ knowledge base
    def kb_semantic(self, on):
        from app.utils import knowledge
        if getattr(self, "_loading", False):
            return
        knowledge.set_semantic(bool(on))
        if on:
            self.ui.label_kb.setText("Lade das Bedeutungs-Modell (beim ersten Mal ca. 470 MB) und berechne die Vektoren …")
            self.kb_index()

    def refresh_kb(self):
        from app.utils import knowledge
        self._loading = True
        self.ui.checkBox_kb_semantic.setChecked(knowledge.semantic_enabled())
        self._loading = False
        self.ui.listWidget_kb.clear()
        for f in knowledge.user_folders():
            self.ui.listWidget_kb.addItem(f)
        if self.ui.listWidget_kb.count() == 0:
            self.ui.listWidget_kb.addItem("(noch kein Ordner gewählt)")
        self._kb_status()

    def _kb_status(self):
        from app.utils import knowledge
        if not self.ui.label_kb.isVisible():
            return
        s = knowledge.status()
        text = f"{s['files']} Dateien, {s['chunks']} Abschnitte im Index."
        if s["running"]:
            text += f"  Liest gerade … ({knowledge.progress['done']}/{knowledge.progress['files']}) {s['message']}"
        elif s["message"]:
            text += "  " + s["message"]
        self.ui.label_kb.setText(text)

    def kb_add(self):
        from app.utils import knowledge
        folder = QtWidgets.QFileDialog.getExistingDirectory(None, "Ordner mit Dokumenten wählen")
        if folder:
            knowledge.save_folders(knowledge.user_folders() + [folder])
            self.refresh_kb()
            self.kb_index()

    def kb_remove(self):
        from app.utils import knowledge
        gone = {i.text() for i in self.ui.listWidget_kb.selectedItems()}
        if gone:
            knowledge.save_folders([f for f in knowledge.user_folders() if f not in gone])
            self.refresh_kb()
            self.kb_index()

    def kb_index(self):
        from app.utils import knowledge
        if not knowledge.folders() and not knowledge.status()["files"]:
            self.ui.label_kb.setText("Wähle zuerst einen Ordner.")
            return
        threading.Thread(target=knowledge.reindex, daemon=True).start()

    # ------------------------------------------------------------------ journal / mood
    def _save_mood(self, value):
        if getattr(self, "_loading", False):
            return
        try:
            self._settings().update_main_setting("mood_aware", bool(value))
        except Exception:
            logger.exception("could not save mood_aware")

    def _save_voice_mood(self, value):
        if getattr(self, "_loading", False):
            return
        try:
            self._settings().update_main_setting("voice_mood", bool(value))
        except Exception:
            logger.exception("could not save voice_mood")

    def refresh_journal(self):
        from app.utils import journal
        lw = self.ui.listWidget_journal
        lw.clear()
        for e in sorted(journal.entries(45), key=lambda i: (i["date"], i["time"]), reverse=True):
            item = QtWidgets.QListWidgetItem(f"{e['date']} {e['time']}  {e['text']}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, e["id"])
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(noch keine Einträge)")

    def delete_journal(self):
        from app.utils import journal
        for item in self.ui.listWidget_journal.selectedItems():
            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if key:
                journal.remove(key)
        self.refresh_journal()

    # ------------------------------------------------------------------ activity log
    def refresh_activity(self):
        from app.utils import tool_log
        lw = self.ui.listWidget_activity
        lw.clear()
        today = datetime.now().strftime("%Y-%m-%d")
        for e in tool_log.read_with_undo(200):
            if not str(e.get("t", "")).startswith(today):
                continue
            mark = "✓" if e.get("success") else "⚠"
            back = "  ↶ rückgängig gemacht" if e.get("undone") else ("  ↶" if e.get("undo") else "")
            args = str(e.get("args", ""))
            try:
                a = json.loads(args)
                args = ", ".join(f"{k}={v}" for k, v in a.items() if k not in ("quick",))[:70]
            except Exception:
                args = args[:70]
            item = QtWidgets.QListWidgetItem(f"{str(e['t'])[11:16]}  {mark} {e.get('tool')}: {args}  →  {str(e.get('result', ''))[:70]}{back}")
            if e.get("undo") and not e.get("undone"):
                item.setData(QtCore.Qt.ItemDataRole.UserRole, e.get("id"))
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(heute noch nichts)")

    def undo_selected(self):
        from app.utils import tool_log
        items = self.ui.listWidget_activity.selectedItems()
        key = items[0].data(QtCore.Qt.ItemDataRole.UserRole) if items else ""
        if items and not key:
            self.ui.label_activity.setText("Dieser Eintrag lässt sich nicht rückgängig machen.")
            return
        ok, text = tool_log.undo(key or "")
        self.ui.label_activity.setText(text)
        self.refresh_activity()
        self.refresh_lists()
        self.refresh_memory()
        self._refresh_reminders_events()

    def _refresh_reminders_events(self):
        try:
            self.refresh_list()
        except Exception:
            logger.debug("refresh failed", exc_info=True)

    # ------------------------------------------------------------------ self test
    def run_selftest(self):
        from app.utils import selftest
        if self.signals is None:
            self.ui.label_selftest.setText("Der Selbsttest ist erst nach dem Start des Programms verfügbar.")
            return
        self.ui.label_selftest.setText("Prüfe alles … (kann ein paar Sekunden dauern)")
        self.ui.pushButton_selftest.setEnabled(False)

        def run():
            results = selftest.run_all(self.signals)
            return results, selftest.summary(results)
        self._bg("selftest", run)

    # ------------------------------------------------------------------ memory / AI behaviour
    def _settings(self):
        from app.configuration.configuration import ConfigurationSettings
        return ConfigurationSettings()

    def _load_ai(self):
        try:
            self.ui.checkBox_llm_thinking.setChecked(bool(self._settings().get_main_setting("llm_thinking")))
            mood_on = self._settings().get_main_setting("mood_aware")
            self.ui.checkBox_mood_aware.setChecked(True if mood_on is None else bool(mood_on))
            self.ui.checkBox_voice_mood.setChecked(bool(self._settings().get_main_setting("voice_mood")))
        except Exception:
            logger.debug("could not read llm_thinking", exc_info=True)

    def _save_ai(self, value):
        if getattr(self, "_loading", False):
            return
        try:
            self._settings().update_main_setting("llm_thinking", bool(value))
        except Exception:
            logger.exception("could not save llm_thinking")

    def refresh_memory(self):
        from app.utils import user_memory
        lw = self.ui.listWidget_memory
        lw.clear()
        for it in user_memory.list_items():
            item = QtWidgets.QListWidgetItem(f"{it['text']}   ({it.get('created', '')})")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, it["id"])
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(noch nichts gemerkt)")

    def delete_memory(self):
        from app.utils import user_memory
        for item in self.ui.listWidget_memory.selectedItems():
            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if key:
                user_memory.forget(key)
        self.refresh_memory()

    # ------------------------------------------------------------------ routines
    def _load_routines(self):
        from app.utils import routines
        cfg = routines.load()
        ui = self.ui
        m, n = cfg["morning"], cfg["night"]
        ui.lineEdit_routine_location.setText(cfg.get("location", ""))
        ui.checkBox_routine_morning.setChecked(bool(m.get("enabled")))
        try:
            hh, mm = [int(x) for x in str(m.get("time", "07:30")).split(":")[:2]]
            ui.timeEdit_routine.setTime(QtCore.QTime(hh, mm))
        except ValueError:
            pass
        for i, cb in enumerate(ui.checkBox_routine_days):
            cb.setChecked(i in m.get("days", []))
        for key, cb in ui.checkBox_routine_inc.items():
            cb.setChecked(bool(m.get(key, True)))
        for key, cb in ui.checkBox_routine_night.items():
            cb.setChecked(bool(n.get(key, True)))
        ui.checkBox_routine_greet.setChecked(bool(cfg.get("greeting_triggers", True)))
        cm = cfg.get("commute", {})
        ui.lineEdit_commute_home.setText(cm.get("home", ""))
        ui.spinBox_commute_buffer.setValue(int(cm.get("buffer", 10)))
        ui.checkBox_commute_on.setChecked(bool(cm.get("enabled", True)))
        ui.checkBox_rain_alert.setChecked(bool(cfg.get("rain_alert", True)))
        ui.checkBox_report.setChecked(bool(cfg.get("report", {}).get("enabled", False)))
        pr = cfg.get("presence", {})
        ui.checkBox_presence.setChecked(bool(pr.get("enabled", False)))
        for key, e in ui.presence_fields.items():
            e.setText(str(pr.get(key, "")))
        try:
            from app.utils import mood as _mood
            summary = _mood.summary(14)
            ui.label_mood.setText("Stimmung der letzten 14 Tage (grobe Einschätzung aus deinen Worten): " + (summary or "nichts Auffälliges"))
        except Exception:
            pass
        ui.comboBox_commute_mode.setCurrentIndex(max(0, ui.comboBox_commute_mode.findData(cm.get("mode", "car"))))
        idx = ui.comboBox_routine_output.findData(m.get("output", "auto"))
        ui.comboBox_routine_output.setCurrentIndex(max(0, idx))

    def _save_routines(self, *_):
        if getattr(self, "_loading", False):
            return
        from app.utils import routines
        cfg = routines.load()
        ui = self.ui
        cfg["location"] = ui.lineEdit_routine_location.text().strip()
        cfg["greeting_triggers"] = ui.checkBox_routine_greet.isChecked()
        cfg["rain_alert"] = ui.checkBox_rain_alert.isChecked()
        cfg["report"] = {**cfg.get("report", {}), "enabled": ui.checkBox_report.isChecked(), "day": 6, "time": "18:00"}
        cfg["presence"] = {**cfg.get("presence", {}), "enabled": ui.checkBox_presence.isChecked(), **{k: e.text().strip() for k, e in ui.presence_fields.items()}}
        cfg["commute"] = {"home": ui.lineEdit_commute_home.text().strip(), "mode": ui.comboBox_commute_mode.currentData() or "car",
                          "buffer": ui.spinBox_commute_buffer.value(), "enabled": ui.checkBox_commute_on.isChecked()}
        m = cfg["morning"]
        m["enabled"] = ui.checkBox_routine_morning.isChecked()
        m["time"] = ui.timeEdit_routine.time().toString("HH:mm")
        m["days"] = [i for i, cb in enumerate(ui.checkBox_routine_days) if cb.isChecked()]
        m["output"] = ui.comboBox_routine_output.currentData() or "auto"
        for key, cb in ui.checkBox_routine_inc.items():
            m[key] = cb.isChecked()
        for key, cb in ui.checkBox_routine_night.items():
            cfg["night"][key] = cb.isChecked()
        routines.save(cfg)

    def test_weather(self):
        from app.utils import routines, weather
        cfg = routines.load()
        cfg["location"] = self.ui.lineEdit_routine_location.text().strip()
        cfg["place"] = {}
        routines.save(cfg)
        self.ui.label_routine_weather.setText("Teste …")

        def run():
            text, place = weather.weather_text(cfg["location"], None, "today")
            if place:
                c2 = routines.load()
                c2["place"] = place
                routines.save(c2)
            return place is not None, text
        self._bg("weather", run)

    def _test(self, name):
        if self.signals is None:
            return
        import asyncio
        asyncio.ensure_future(self.signals.run_routine(name, "test"))

    # ------------------------------------------------------------------ calendar
    def save_ics(self):
        from app.utils import organizer
        urls = [u.strip() for u in self.ui.plainTextEdit_organizer_ics.toPlainText().splitlines() if u.strip()]
        cfg = organizer.config()
        cfg["ics"] = urls
        organizer.save_config(cfg)
        self.ui.label_organizer_ics.setText("Teste …")

        def test():
            now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            events, problems = organizer.events_between(now, now + timedelta(days=30))
            return len([e for e in events if e["source"] == "Kalender"]), problems
        self._bg("ics", test)

    # ------------------------------------------------------------------ mail
    def save_mail(self):
        from app.utils import organizer
        ui = self.ui
        cfg = organizer.config()
        old = cfg.get("imap", {})
        password = ui.lineEdit_mail_password.text() or old.get("password", "")
        try:
            port = int(ui.lineEdit_mail_port.text().strip() or 993)
        except ValueError:
            port = 993
        cfg["imap"] = {"host": ui.lineEdit_mail_host.text().strip(), "port": port, "user": ui.lineEdit_mail_user.text().strip(),
                       "password": password, "folder": ui.lineEdit_mail_folder.text().strip() or "INBOX"}
        organizer.save_config(cfg)
        ui.label_mail_status.setText("Teste die Verbindung …")
        self._bg("mail", organizer.mail_test)

    def remove_mail(self):
        from app.utils import organizer
        cfg = organizer.config()
        cfg["imap"] = {}
        organizer.save_config(cfg)
        self._load_fields()
        self.ui.label_mail_status.setText("Mail-Konto entfernt.")

    # ------------------------------------------------------------------ list
    def refresh_list(self):
        from app.utils import organizer
        lw = self.ui.listWidget_organizer
        lw.clear()
        for r in organizer.list_reminders():
            try:
                when = organizer.fmt(datetime.fromisoformat(r["when"]))
            except Exception:
                when = r.get("when", "")
            rep = f" (wiederholt {r['repeat']})" if r.get("repeat") else ""
            item = QtWidgets.QListWidgetItem(f"⏰ {when}  {r['text']}{rep}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("reminder", r["id"]))
            lw.addItem(item)
        now = datetime.now()
        for e in organizer._local_events(now, now + timedelta(days=365)):
            item = QtWidgets.QListWidgetItem(f"📅 {organizer.fmt(e['start'], e['all_day'])}  {e['title']}" + (f" @ {e['location']}" if e["location"] else ""))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, ("event", e["id"]))
            lw.addItem(item)
        if lw.count() == 0:
            lw.addItem("(nichts eingetragen)")

    def delete_selected(self):
        from app.utils import organizer
        for item in self.ui.listWidget_organizer.selectedItems():
            data = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if not data:
                continue
            if data[0] == "reminder":
                organizer.cancel_reminder(data[1])
            else:
                organizer.delete_event(data[1])
        self.refresh_list()

    def _on_result(self, name, data):
        if name == "ics":
            if isinstance(data, Exception):
                self.ui.label_organizer_ics.setText(f"Fehler: {data}")
                return
            count, problems = data
            text = f"{count} Termin(e) in den nächsten 30 Tagen gefunden." if not problems else "; ".join(problems)
            self.ui.label_organizer_ics.setStyleSheet(f"color: {'#8BE9A8' if not problems else '#F6C177'}; border: none; background: transparent;")
            self.ui.label_organizer_ics.setText(text)
        elif name == "selftest":
            self.ui.pushButton_selftest.setEnabled(True)
            if isinstance(data, Exception):
                self.ui.label_selftest.setText(f"Selbsttest fehlgeschlagen: {data}")
                return
            results, summary = data
            icon = {"ok": "🟢", "warn": "🟡", "fail": "🔴", "off": "⚪"}
            import html
            lines = [f"<b>{html.escape(summary)}</b>"] + [f"{icon.get(r['state'], '')} <b>{html.escape(r['name'])}</b> – {html.escape(r['detail'])}" for r in results]
            self.ui.label_selftest.setText("<br>".join(lines))
        elif name == "weather":
            ok, text = (False, str(data)) if isinstance(data, Exception) else data
            self.ui.label_routine_weather.setStyleSheet(f"color: {'#8BE9A8' if ok else '#F6C177'}; border: none; background: transparent;")
            self.ui.label_routine_weather.setText(text.replace("\n", "  ·  "))
        elif name == "mail":
            ok, text = (False, str(data)) if isinstance(data, Exception) else data
            self.ui.label_mail_status.setStyleSheet(f"color: {'#8BE9A8' if ok else '#F6C177'}; border: none; background: transparent;")
            self.ui.label_mail_status.setText(text)
