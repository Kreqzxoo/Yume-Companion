// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in this folder.
// Yume LLM Server - turns another PC into an AI server for Yume Companion (llama.cpp, Yume style).
// Compiled with the C# 5 compiler that ships with Windows (no SDK needed). Language/UI strings: German + English.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Management;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Yume LLM Server")]
[assembly: AssemblyDescription("Yume LLM Server - AI server for Yume Companion")]
[assembly: AssemblyCompany("Kreqzxoo")]
[assembly: AssemblyProduct("Yume LLM Server")]
[assembly: AssemblyCopyright("Copyright (c) 2026 Kreqzxoo")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace YumeLlmServer
{
    // ------------------------------------------------------------------ entry
    static class Program
    {
        public const string Version = "1.0.0";
        [STAThread]
        static void Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "--exit")        // used by the installer / uninstaller to close a running instance
            {
                try { EventWaitHandle ev = EventWaitHandle.OpenExisting("Global\\YumeLlmServerExit"); ev.Set(); Thread.Sleep(3000); } catch { }
                return;
            }
            bool created;
            using (Mutex m = new Mutex(true, "Global\\YumeLlmServerSingleton", out created))
            {
                if (!created)
                {
                    MessageBox.Show(Loc.T("already"), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072 | (SecurityProtocolType)768;
                if (args.Length > 0 && args[0] == "--selftest") { SelfTest.Run(args.Length > 1 ? args[1] : "cpu"); return; }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm(args));
            }
        }
    }

    static class SelfTest
    {
        public static void Run(string type)
        {
            string log = Path.Combine(Paths.Root, "selftest.log");
            Directory.CreateDirectory(Paths.Root);
            Action<string> w = delegate(string s) { File.AppendAllText(log, DateTime.Now.ToString("HH:mm:ss") + "  " + s + Environment.NewLine); };
            try
            {
                File.WriteAllText(log, "");
                if (type == "sd" || type == "sdvulkan")
                {
                    Hardware h2 = Hardware.Detect();
                    string st = type == "sd" ? "cpu" : "vulkan";
                    w("IMAGE ENGINE install " + st);
                    ImageEngine.Install(st, h2, delegate(double f, string text) { }, null);
                    string sexe = ImageEngine.ServerExe(st);
                    w("IMAGE ENGINE exe=" + sexe + " version=" + ImageEngine.InstalledVersion(st));
                    w("DEVICES " + Hardware.Run(sexe, "--list-devices", 20000).Replace((char)10, ' '));
                    w("SELFTEST OK");
                    return;
                }
                Hardware hw = Hardware.Detect();
                w("HARDWARE " + hw.Describe() + " | nvidia=" + hw.Nvidia + " driver=" + hw.DriverMajor + " usable=" + hw.UsableGb.ToString("0.0"));
                List<ModelInfo> all = Catalog.All();
                ModelInfo recL = hw.Recommend(all, "llm"), recV = hw.Recommend(all, "vision");
                w("RECOMMENDED llm=" + (recL != null ? recL.Name : "-") + " vision=" + (recV != null ? recV.Name : "-"));
                w("ENGINE install " + type + " (vc missing: " + Engine.VcRuntimeMissing() + ")");
                Engine.Install(type, hw, delegate(double f, string text) { }, null);
                string exe = Engine.ServerExe(type);
                w("ENGINE exe=" + exe + " version=" + Engine.InstalledVersion(type));
                ModelInfo m = all.First(delegate(ModelInfo x) { return x.Id == "gemma3-1b"; });
                string dest = Path.Combine(Paths.Models, m.File);
                if (!File.Exists(dest))
                {
                    w("MODEL download " + m.File);
                    DateTime t0 = DateTime.Now;
                    Net.Download("https://huggingface.co/" + m.Repo + "/resolve/main/" + m.File, dest, null, null);
                    w("MODEL done " + new FileInfo(dest).Length / 1048576 + " MB in " + (DateTime.Now - t0).TotalSeconds.ToString("0") + " s");
                }
                AppSettings s = new AppSettings(); s.Port = 18080; s.Lan = false; s.Ctx = 2048;
                ServerRunner r = new ServerRunner();
                r.LogLine += delegate(string l) { };
                r.Start(exe, type != "cpu", s, m, null, null, null, false);
                int waited = 0;
                while (!r.LlmReady && waited < 240 && r.Running) { Thread.Sleep(1000); waited++; }
                w("SERVER ready=" + r.LlmReady + " after " + waited + " s running=" + r.Running);
                if (r.LlmReady)
                {
                    w("MODELS " + Net.GetString("http://127.0.0.1:18080/v1/models").Substring(0, 120).Replace((char)10, ' '));
                    HttpWebRequest rq = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:18080/v1/chat/completions");
                    rq.Method = "POST"; rq.ContentType = "application/json"; rq.Timeout = 120000;
                    byte[] body = Encoding.UTF8.GetBytes("{\"messages\":[{\"role\":\"user\",\"content\":\"Say hi in one short sentence.\"}],\"max_tokens\":24}");
                    using (Stream st = rq.GetRequestStream()) st.Write(body, 0, body.Length);
                    using (WebResponse resp = rq.GetResponse()) using (StreamReader sr = new StreamReader(resp.GetResponseStream())) w("CHAT " + sr.ReadToEnd().Replace((char)10, ' '));
                }
                r.Stop();
                w("STOPPED running=" + r.Running);
                w("SELFTEST OK");
            }
            catch (Exception ex) { w("SELFTEST FAILED: " + ex); }
        }
    }

    // ------------------------------------------------------------------ strings
    static class Loc
    {
        public static bool German = System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "de";
        static readonly Dictionary<string, string[]> S = new Dictionary<string, string[]>
        {
            {"already", new[]{"Yume LLM Server läuft bereits (Symbol im Infobereich der Taskleiste).", "Yume LLM Server is already running (see the tray icon)."}},
            {"subtitle", new[]{"Mach diesen PC zum KI-Server für Yume Companion", "Turn this PC into the AI server for Yume Companion"}},
            {"stopped", new[]{"Server gestoppt", "Server stopped"}},
            {"starting", new[]{"Modell wird geladen ...", "Loading model ..."}},
            {"running", new[]{"Server läuft", "Server running"}},
            {"start", new[]{"Server starten", "Start server"}},
            {"stop", new[]{"Server stoppen", "Stop server"}},
            {"yourpc", new[]{"DEIN PC", "YOUR PC"}},
            {"gpu", new[]{"Grafikkarte", "Graphics card"}},
            {"nogpu", new[]{"Keine dedizierte Grafikkarte erkannt – es wird die CPU genutzt (langsamer).", "No dedicated graphics card detected - the CPU is used (slower)."}},
            {"ram", new[]{"Arbeitsspeicher", "Memory"}},
            {"engine", new[]{"Engine", "Engine"}},
            {"engine_ok", new[]{"installiert", "installed"}},
            {"engine_missing", new[]{"noch nicht installiert", "not installed yet"}},
            {"engine_install", new[]{"Engine installieren", "Install engine"}},
            {"engine_update", new[]{"Engine aktualisieren", "Update engine"}},
            {"update_short", new[]{"Aktualisieren", "Update"}},
            {"engine_auto", new[]{"Automatisch", "Automatic"}},
            {"tab_llm", new[]{"Sprache", "Language"}},
            {"tab_image", new[]{"Bilder", "Images"}},
            {"settings", new[]{"Einstellungen", "Settings"}},
            {"s_net", new[]{"NETZWERK", "NETWORK"}}, {"s_perf", new[]{"LEISTUNG", "PERFORMANCE"}}, {"s_engine", new[]{"ENGINES", "ENGINES"}}, {"s_win", new[]{"WINDOWS", "WINDOWS"}},
            {"port_hint", new[]{"Vision = Port + 1, Bilder = Port + 2", "Vision = port + 1, images = port + 2"}},
            {"eng_llm", new[]{"Sprache & Vision", "Language & vision"}}, {"eng_img", new[]{"Bilder", "Images"}},
            {"open_models", new[]{"Modellordner öffnen", "Open models folder"}},
            {"on_llm", new[]{"Sprachmodell beim Start mitstarten", "Start the language model with the server"}},
            {"on_vision", new[]{"Vision-Modell beim Start mitstarten", "Start the vision model with the server"}},
            {"on_image", new[]{"Bild-KI beim Start mitstarten", "Start the image AI with the server"}},
            {"show_all", new[]{"Zu große Modelle anzeigen ({0})", "Show models that are too big ({0})"}},
            {"only_fit", new[]{"Nur passende Modelle zeigen", "Show only matching models"}},
            {"stop_first", new[]{"Bitte zuerst den Server stoppen.", "Please stop the server first."}},
            {"need_engine_img", new[]{"Die Bild-Engine (stable-diffusion.cpp) ist noch nicht installiert. Jetzt herunterladen und installieren?", "The image engine (stable-diffusion.cpp) is not installed yet. Download and install it now?"}},
            {"hint_llm", new[]{"In Yume Companion: Sprachmodell & APIs → „Auf einem anderen PC im Netzwerk“ → diese Adresse (oder Netzwerk durchsuchen).", "In Yume Companion: Language model & APIs > \"On another PC\" > this address (or search the network)."}},
            {"hint_vision", new[]{"In Yume Companion: Vision-KI → „Auf einem anderen PC im Netzwerk“ → diese Adresse.", "In Yume Companion: Vision AI > \"On another PC\" > this address."}},
            {"hint_image", new[]{"In Yume Companion: Bildgenerierung → „Auf einem anderen PC im Netzwerk“ → diese Adresse (Dienst: Automatic1111).", "In Yume Companion: Image generation > \"On another PC\" > this address (service: Automatic1111)."}},
            {"tab_vision", new[]{"Vision", "Vision"}},
            {"tab_tools", new[]{"Werkzeuge", "Tools"}},
            {"on_tools", new[]{"Werkzeug-Modell beim Start mitstarten", "Start the tool model with the server"}},
            {"hint_tools", new[]{"Optional – nur EIN Modell nötig. In Yume Companion: Werkzeuge → „Werkzeug-Modell extern“ → diese Adresse. Ohne dieses Modell übernimmt das Sprachmodell die Werkzeuge.", "Optional - one model is enough. In Yume Companion: Tools > \"External tool model\" > this address. Without it the language model handles the tools."}},
            {"rec", new[]{"★ Empfohlen für deinen PC", "★ Recommended for your PC"}},
            {"fits", new[]{"✓ Passt gut", "✓ Fits well"}},
            {"tight", new[]{"≈ Knapp – teils im RAM, langsamer", "≈ Tight - partly in RAM, slower"}},
            {"toobig", new[]{"✗ Zu groß für deinen PC – sehr langsam", "✗ Too big for your PC - very slow"}},
            {"big_confirm", new[]{"„{0}“ ist für diesen PC sehr groß (braucht ca. {1:0} GB Speicher). Es läuft dann nur sehr langsam oder gar nicht. Trotzdem herunterladen?", "\"{0}\" is very big for this PC (needs about {1:0} GB memory). It will run very slowly or not at all. Download anyway?"}},
            {"big_start", new[]{"Das gewählte Modell passt nicht komplett in den Grafikspeicher. llama.cpp lagert dann Teile in den Arbeitsspeicher aus – das ist deutlich langsamer. Trotzdem starten?", "The selected model does not fit completely into graphics memory. llama.cpp will move parts to RAM - much slower. Start anyway?"}},
            {"download", new[]{"Herunterladen", "Download"}},
            {"cancel", new[]{"Abbrechen", "Cancel"}},
            {"select", new[]{"Auswählen", "Select"}},
            {"active", new[]{"● Aktiv", "● Active"}},
            {"remove", new[]{"Löschen", "Delete"}},
            {"none", new[]{"Keins (aus)", "None (off)"}},
            {"conn", new[]{"VERBINDUNG ZU YUME COMPANION", "CONNECTION TO YUME COMPANION"}},
            {"conn_hint", new[]{"In Yume Companion: Einstellungen → Sprachmodell & APIs → „Auf einem anderen PC im Netzwerk“ → diese Adresse eintragen (oder Netzwerk durchsuchen).", "In Yume Companion: Settings > Language model & APIs > \"On another PC in the network\" > enter this address (or search the network)."}},
            {"conn_hint_vision", new[]{"Vision: in Yume Companion unter Vision-KI „Auf einem anderen PC“ wählen und diese Adresse eintragen.", "Vision: in Yume Companion choose \"On another PC\" under Vision AI and enter this address."}},
            {"copy", new[]{"Kopieren", "Copy"}},
            {"copied", new[]{"Kopiert", "Copied"}},
            {"port", new[]{"Port", "Port"}},
            {"ctx", new[]{"Kontext", "Context"}},
            {"key", new[]{"Zugangsschlüssel (optional)", "Access key (optional)"}},
            {"lan", new[]{"Im Heimnetz erreichbar", "Reachable in the home network"}},
            {"autostart", new[]{"Mit Windows starten", "Start with Windows"}},
            {"autorun", new[]{"Server beim Programmstart automatisch starten", "Start the server automatically when the program starts"}},
            {"log", new[]{"Protokoll", "Log"}},
            {"firewall", new[]{"Firewall prüfen", "Check firewall"}},
            {"fw_ask", new[]{"Damit Yume Companion auf deinem Hauptrechner diesen Server erreichen kann, muss die Windows-Firewall die Ports freigeben. Jetzt einrichten? (Windows fragt nach Administratorrechten)", "For Yume Companion on your main PC to reach this server, the Windows firewall has to allow the ports. Set it up now? (Windows will ask for administrator rights)"}},
            {"fw_done", new[]{"Die Firewall-Freigabe wurde eingerichtet.", "The firewall rule was created."}},
            {"fw_fail", new[]{"Die Freigabe konnte nicht eingerichtet werden (Administratorrechte nötig).", "Could not create the rule (administrator rights required)."}},
            {"need_engine", new[]{"Die Engine (llama.cpp) ist noch nicht installiert. Jetzt herunterladen und installieren?", "The engine (llama.cpp) is not installed yet. Download and install it now?"}},
            {"need_model", new[]{"Bitte zuerst ein Modell herunterladen und auswählen.", "Please download and select a model first."}},
            {"installing", new[]{"Engine wird installiert: {0}", "Installing the engine: {0}"}},
            {"engine_done", new[]{"Engine bereit ({0}).", "Engine ready ({0})."}},
            {"engine_fail", new[]{"Die Engine konnte nicht installiert werden: {0}", "Could not install the engine: {0}"}},
            {"vc", new[]{"Visual-C++-Laufzeit wird installiert ...", "Installing the Visual C++ runtime ..."}},
            {"dl_fail", new[]{"Download fehlgeschlagen: {0}", "Download failed: {0}"}},
            {"ready_for", new[]{"Bereit – Yume Companion kann sich jetzt verbinden.", "Ready - Yume Companion can connect now."}},
            {"crashed", new[]{"Der Server wurde unerwartet beendet. Details im Protokoll.", "The server exited unexpectedly. See the log for details."}},
            {"tray_open", new[]{"Öffnen", "Open"}},
            {"tray_quit", new[]{"Beenden", "Quit"}},
            {"tray_run", new[]{"Läuft im Hintergrund weiter. Rechtsklick auf das Symbol zum Beenden.", "Keeps running in the background. Right-click the icon to quit."}},
            {"size", new[]{"Größe", "Size"}},
            {"vram_need", new[]{"braucht ca. {0:0.0} GB Speicher", "needs about {0:0.0} GB memory"}},
            {"tip_title", new[]{"Tipp", "Tip"}},
            {"tip_text", new[]{"Beide Server (Sprache + Vision) laufen gleichzeitig. Wähle bei wenig Grafikspeicher kleinere Modelle oder nur eins von beiden.", "Both servers (language + vision) run at the same time. With little graphics memory pick smaller models or only one of them."}},
            {"upd_engine", new[]{"Engine-Version", "Engine version"}},
        };
        public static string T(string key)
        {
            string[] v;
            if (!S.TryGetValue(key, out v)) return key;
            return German ? v[0] : v[1];
        }
        public static string F(string key, params object[] a) { return string.Format(T(key), a); }
    }

    // ------------------------------------------------------------------ theme + controls
    static class Theme
    {
        public static readonly Color Bg = Color.FromArgb(21, 16, 31);
        public static readonly Color Panel = Color.FromArgb(31, 24, 48);
        public static readonly Color Panel2 = Color.FromArgb(39, 31, 58);
        public static readonly Color Line = Color.FromArgb(70, 255, 143, 199);
        public static readonly Color Pink = Color.FromArgb(255, 143, 199);
        public static readonly Color Pink2 = Color.FromArgb(255, 194, 226);
        public static readonly Color Lav = Color.FromArgb(182, 156, 255);
        public static readonly Color Text = Color.FromArgb(243, 236, 247);
        public static readonly Color Muted = Color.FromArgb(169, 156, 189);
        public static readonly Color Ok = Color.FromArgb(110, 231, 160);
        public static readonly Color Warn = Color.FromArgb(246, 193, 119);
        public static readonly Color Bad = Color.FromArgb(255, 143, 163);
        public static Font F(float size, FontStyle st) { return new Font("Segoe UI", size, st, GraphicsUnit.Point); }

        public static GraphicsPath Round(Rectangle r, int radius)
        {
            GraphicsPath p = new GraphicsPath();
            int d = radius * 2;
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }
    }

    class RoundButton : Control
    {
        bool hover, down;
        public bool Primary = true;
        public bool Selected;
        public RoundButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.Selectable, false);
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            Cursor = Cursors.Hand;
            Font = Theme.F(9.5f, FontStyle.Bold);
            Height = 36;
        }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = true; Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { down = false; Invalidate(); base.OnMouseUp(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }
        protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Parent != null ? Parent.BackColor : Theme.Bg);
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (GraphicsPath path = Theme.Round(r, Math.Max(8, Height / 2 - 2)))
            {
                int a = Enabled ? (down ? 210 : hover ? 255 : 235) : 90;
                if (Primary || Selected)
                {
                    using (LinearGradientBrush br = new LinearGradientBrush(r, Color.FromArgb(a, 255, 143, 199), Color.FromArgb(a, 182, 156, 255), 0f))
                        g.FillPath(br, path);
                }
                else
                {
                    using (SolidBrush br = new SolidBrush(Color.FromArgb(hover ? 60 : 36, 255, 143, 199))) g.FillPath(br, path);
                    using (Pen pen = new Pen(Color.FromArgb(Enabled ? 140 : 60, 255, 143, 199))) g.DrawPath(pen, path);
                }
            }
            Color tc = (Primary || Selected) ? Color.FromArgb(40, 18, 46) : Theme.Text;
            if (!Enabled) tc = Color.FromArgb(150, tc);
            TextRenderer.DrawText(g, Text, Font, new Rectangle(0, 0, Width, Height), tc, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding);
        }
    }

    class Card : Panel
    {
        public string Title = "";
        public Card() { DoubleBuffered = true; BackColor = Theme.Bg; Padding = new Padding(16); }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (GraphicsPath p = Theme.Round(r, 14))
            {
                using (SolidBrush b = new SolidBrush(Theme.Panel)) g.FillPath(b, p);
                using (Pen pen = new Pen(Theme.Line)) g.DrawPath(pen, p);
            }
            if (Title.Length > 0)
                TextRenderer.DrawText(g, Title, Theme.F(8.5f, FontStyle.Bold), new Point(16, 11), Theme.Lav);
        }
    }

    class SlimProgress : Control
    {
        double v;
        public SlimProgress() { SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true); Height = 10; }
        public double Value { get { return v; } set { v = Math.Max(0, Math.Min(1, value)); Invalidate(); } }
        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Parent != null ? Parent.BackColor : Theme.Bg);
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (GraphicsPath p = Theme.Round(r, Height / 2)) using (SolidBrush b = new SolidBrush(Color.FromArgb(60, 255, 255, 255))) g.FillPath(b, p);
            int w = (int)((Width - 1) * v);
            if (w > Height)
            {
                Rectangle fr = new Rectangle(0, 0, w, Height - 1);
                using (GraphicsPath p = Theme.Round(fr, Height / 2))
                using (LinearGradientBrush b = new LinearGradientBrush(fr, Theme.Pink, Theme.Lav, 0f)) g.FillPath(b, p);
            }
        }
    }

    // ------------------------------------------------------------------ data
    class ModelInfo
    {
        public string Id, Name, Repo, File, Mmproj, Desc, Kind;
        public double SizeGb, MmprojGb, NeedOverride;
        public bool NoAuto;                 // never picked as the automatic recommendation (MoE, reasoning, special purpose)
        public double NeedGb { get { return NeedOverride > 0 ? NeedOverride : (SizeGb + MmprojGb) * 1.12 + (Kind == "vision" ? 0.8 : 1.2); } }
    }

    static class Catalog
    {
        static ModelInfo M(string kind, string id, string name, string repo, string file, double gb, string desc, string mm, double mmgb)
        {
            return new ModelInfo { Kind = kind, Id = id, Name = name, Repo = repo, File = file, SizeGb = gb, Desc = desc, Mmproj = mm, MmprojGb = mmgb };
        }
        static ModelInfo Img(string id, string name, string repo, string file, double gb, double need, string desc)
        {
            return new ModelInfo { Kind = "image", Id = id, Name = name, Repo = repo, File = file, SizeGb = gb, NeedOverride = need, Desc = desc };
        }
        public static List<ModelInfo> All()
        {
            bool de = Loc.German;
            List<ModelInfo> l = new List<ModelInfo>();
            l.Add(M("llm", "gemma3-1b", "Gemma 3 1B", "ggml-org/gemma-3-1b-it-GGUF", "gemma-3-1b-it-Q4_K_M.gguf", 0.81,
                de ? "Winzig und schnell – läuft auch auf schwachen PCs, einfache Gespräche." : "Tiny and fast - runs on weak PCs, simple chats.", null, 0));
            l.Add(M("llm", "qwen3-1.7b", "Qwen3 1.7B", "Qwen/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q8_0.gguf", 1.83,
                de ? "Klein, aber überraschend gut. Gut für PCs ohne Grafikkarte." : "Small but surprisingly good. Fine for PCs without a graphics card.", null, 0));
            l.Add(M("llm", "llama32-3b", "Llama 3.2 3B", "bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama-3.2-3B-Instruct-Q4_K_M.gguf", 2.02,
                de ? "Flüssiger Allrounder für 4-GB-Grafikkarten." : "Smooth all-rounder for 4 GB graphics cards.", null, 0));
            l.Add(M("llm", "qwen3-4b", "Qwen3 4B", "Qwen/Qwen3-4B-GGUF", "Qwen3-4B-Q4_K_M.gguf", 2.50,
                de ? "Starkes kleines Modell mit Werkzeug-Unterstützung (Yume-Tools)." : "Strong small model with tool support (Yume tools).", null, 0));
            l.Add(M("llm", "gemma3-4b-q8", "Gemma 3 4B (hohe Qualität)", "ggml-org/gemma-3-4b-it-GGUF", "gemma-3-4b-it-Q8_0.gguf", 4.13,
                de ? "Gemma 3 4B in Q8: nahezu verlustfrei, für 6-GB-Karten." : "Gemma 3 4B in Q8: nearly lossless, for 6 GB cards.", null, 0));
            l.Add(M("llm", "llama31-8b", "Llama 3.1 8B", "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", 4.92,
                de ? "Bewährter Allrounder von Meta, sehr viele Feinabstimmungen." : "Proven all-rounder from Meta.", null, 0));
            l.Add(M("llm", "gemma2-9b", "Gemma 2 9B", "bartowski/gemma-2-9b-it-GGUF", "gemma-2-9b-it-Q4_K_M.gguf", 5.76,
                de ? "Sehr natürlicher Schreibstil, gut fürs Rollenspiel." : "Very natural writing style, good for roleplay.", null, 0));
            l.Add(M("llm", "qwen3-8b", "Qwen3 8B", "Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf", 5.03,
                de ? "Bester Kompromiss für 8-GB-Karten: Rollenspiel, Werkzeuge, Browser-Agent." : "Best compromise for 8 GB cards: roleplay, tools, browser agent.", null, 0));
            l.Add(M("llm", "nemo-12b", "Mistral Nemo 12B", "bartowski/Mistral-Nemo-Instruct-2407-GGUF", "Mistral-Nemo-Instruct-2407-Q4_K_M.gguf", 7.48,
                de ? "Beliebt für kreative Geschichten und Charakter-Chats (ab 10 GB)." : "Popular for creative stories and character chats (from 10 GB).", null, 0));
            l.Add(M("llm", "gemma3-12b", "Gemma 3 12B", "ggml-org/gemma-3-12b-it-GGUF", "gemma-3-12b-it-Q4_K_M.gguf", 7.30,
                de ? "Googles starkes Mittelklasse-Modell, sehr gute Texte." : "Google's strong mid-size model, very good writing.", null, 0));
            l.Add(M("llm", "qwen3-14b", "Qwen3 14B", "Qwen/Qwen3-14B-GGUF", "Qwen3-14B-Q4_K_M.gguf", 9.00,
                de ? "Deutlich klüger bei langen Plänen – ab 12 GB Grafikspeicher." : "Much smarter with long plans - from 12 GB graphics memory.", null, 0));
            l.Add(M("llm", "phi4-14b", "Phi-4 14B", "bartowski/phi-4-GGUF", "phi-4-Q4_K_M.gguf", 9.05,
                de ? "Microsofts Denk- und Rechenmodell – eher sachlich als verspielt." : "Microsoft's reasoning model - more factual than playful.", null, 0));
            l.Add(M("llm", "r1-14b", "DeepSeek R1 Distill 14B", "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF", "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf", 8.99,
                de ? "Denkt vor dem Antworten nach (Reasoning). Langsamer, dafür gründlich." : "Thinks before answering (reasoning). Slower but thorough.", null, 0));
            l.Add(M("llm", "gptoss-20b", "gpt-oss 20B", "ggml-org/gpt-oss-20b-GGUF", "gpt-oss-20b-MXFP4.gguf", 12.11,
                de ? "Offenes OpenAI-Modell mit Reasoning und Werkzeugen (ab 16 GB)." : "Open OpenAI model with reasoning and tools (from 16 GB).", null, 0));
            l.Add(M("llm", "mistral-small-24b", "Mistral Small 3.2 24B", "bartowski/mistralai_Mistral-Small-3.2-24B-Instruct-2506-GGUF", "mistralai_Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf", 14.33,
                de ? "Sehr gutes Rollenspiel- und Schreibmodell (ab 20 GB Grafikspeicher)." : "Very good roleplay and writing model (from 20 GB graphics memory).", null, 0));
            l.Add(M("llm", "gemma3-27b", "Gemma 3 27B", "ggml-org/gemma-3-27b-it-GGUF", "gemma-3-27b-it-Q4_K_M.gguf", 16.55,
                de ? "Googles großes Modell: ausdrucksstark und zuverlässig (ab 24 GB)." : "Google's large model: expressive and reliable (from 24 GB).", null, 0));
            l.Add(M("llm", "qwen3-30b-a3b", "Qwen3 30B-A3B (MoE)", "Qwen/Qwen3-30B-A3B-GGUF", "Qwen3-30B-A3B-Q4_K_M.gguf", 18.56,
                de ? "Riesig, aber schnell (Mixture of Experts). Für 24 GB Karten oder 32 GB RAM." : "Huge but fast (mixture of experts). For 24 GB cards or 32 GB RAM.", null, 0));
            l.Add(M("llm", "qwen3-32b", "Qwen3 32B", "Qwen/Qwen3-32B-GGUF", "Qwen3-32B-Q4_K_M.gguf", 19.76,
                de ? "Höchste Qualität bei den „normalen“ Größen. Nur für 24-GB-Karten oder mehr." : "Highest quality of the regular sizes. Only for 24 GB cards or more.", null, 0));
            l.Add(M("llm", "r1-32b", "DeepSeek R1 Distill 32B", "bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF", "DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf", 19.85,
                de ? "Starkes Reasoning-Modell für schwere Aufgaben (24 GB oder mehr)." : "Strong reasoning model for hard tasks (24 GB or more).", null, 0));
            l.Add(M("llm", "llama33-70b", "Llama 3.3 70B", "bartowski/Llama-3.3-70B-Instruct-GGUF", "Llama-3.3-70B-Instruct-Q4_K_M.gguf", 42.52,
                de ? "Sehr groß und sehr gut. Braucht ~48 GB Speicher (Grafikkarte + RAM) – auf schwachen PCs extrem langsam." : "Very large and very good. Needs ~48 GB memory (GPU + RAM) - extremely slow on weak PCs.", null, 0));
            l.Add(M("llm", "qwen25-72b", "Qwen2.5 72B", "bartowski/Qwen2.5-72B-Instruct-GGUF", "Qwen2.5-72B-Instruct-Q4_K_M.gguf", 47.42,
                de ? "Eines der größten offenen Modelle. Braucht ~54 GB Speicher – nur für Workstations." : "One of the largest open models. Needs ~54 GB memory - workstations only.", null, 0));

            l.Add(M("tools", "t-qwen3-4b", "Qwen3 4B", "Qwen/Qwen3-4B-GGUF", "Qwen3-4B-Q4_K_M.gguf", 2.50,
                de ? "Einsteiger: klein und schnell, zuverlässiger Werkzeug-Aufruf (Websuche, Systemwerkzeuge). Ideal als Zweitmodell neben dem Sprachmodell." : "Starter: small and fast, reliable tool calls (web search, system tools). Ideal as a second model next to the language model.", null, 0));
            l.Add(M("tools", "t-qwen3-8b", "Qwen3 8B", "Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf", 5.03,
                de ? "Empfohlen: bester Kompromiss für Browser-Agent, Dateien und mehrstufige Aufgaben (ab 8 GB, besser eigene Grafikkarte)." : "Recommended: best compromise for browser agent, files and multi-step tasks (from 8 GB, ideally its own graphics card).", null, 0));
            l.Add(M("tools", "t-qwen3-14b", "Qwen3 14B", "Qwen/Qwen3-14B-GGUF", "Qwen3-14B-Q4_K_M.gguf", 9.00,
                de ? "Fortgeschritten: deutlich besser bei langen Plänen und GUI-/Computersteuerung (ab 12 GB)." : "Advanced: much better with long plans and GUI / computer control (from 12 GB).", null, 0));
            l.Add(M("tools", "t-qwen25-coder-7b", "Qwen2.5-Coder 7B", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4.68,
                de ? "Spezialist: schreibt Python-/PowerShell-Skripte für „Code ausführen“. Ersetzt kein Hauptmodell." : "Specialist: writes Python / PowerShell scripts for \"run code\". Does not replace a main model.", null, 0));
            l.Add(M("vision", "smolvlm2", "SmolVLM2 2.2B", "ggml-org/SmolVLM2-2.2B-Instruct-GGUF", "SmolVLM2-2.2B-Instruct-Q4_K_M.gguf", 1.11,
                de ? "Sehr klein – versteht Bilder auf fast jedem PC." : "Very small - understands images on almost any PC.", "mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf", 0.59));
            l.Add(M("vision", "qwen25vl-3b", "Qwen2.5-VL 3B", "ggml-org/Qwen2.5-VL-3B-Instruct-GGUF", "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf", 1.93,
                de ? "Gut bei Bildschirminhalten und Text im Bild." : "Good with screen contents and text in images.", "mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf", 0.84));
            l.Add(M("vision", "gemma3-4b", "Gemma 3 4B", "ggml-org/gemma-3-4b-it-GGUF", "gemma-3-4b-it-Q4_K_M.gguf", 2.49,
                de ? "Ausgewogen, beschreibt Bilder natürlich." : "Balanced, describes images naturally.", "mmproj-model-f16.gguf", 0.85));
            l.Add(M("vision", "qwen25vl-7b", "Qwen2.5-VL 7B", "ggml-org/Qwen2.5-VL-7B-Instruct-GGUF", "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf", 4.68,
                de ? "Empfohlen für GUI-Steuerung und Screenshots (ab 8 GB)." : "Recommended for GUI control and screenshots (from 8 GB).", "mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf", 0.85));
            l.Add(M("vision", "gemma3-12b", "Gemma 3 12B", "ggml-org/gemma-3-12b-it-GGUF", "gemma-3-12b-it-Q4_K_M.gguf", 7.30,
                de ? "Beste Bildverständnis-Qualität (ab 12 GB)." : "Best image understanding quality (from 12 GB).", "mmproj-model-f16.gguf", 0.85));
            l.Add(M("vision", "gemma3-27b-v", "Gemma 3 27B", "ggml-org/gemma-3-27b-it-GGUF", "gemma-3-27b-it-Q4_K_M.gguf", 16.55,
                de ? "Sehr starkes Bildverständnis (ab 24 GB)." : "Very strong image understanding (from 24 GB).", "mmproj-model-f16.gguf", 0.86));
            l.Add(M("vision", "qwen25vl-32b", "Qwen2.5-VL 32B", "ggml-org/Qwen2.5-VL-32B-Instruct-GGUF", "Qwen2.5-VL-32B-Instruct-Q4_K_M.gguf", 19.85,
                de ? "Top bei Bildschirm-Inhalten und GUI-Steuerung (ab 24 GB)." : "Top for screen contents and GUI control (from 24 GB).", "mmproj-Qwen2.5-VL-32B-Instruct-Q8_0.gguf", 0.73));
            l.Add(M("vision", "qwen25vl-72b", "Qwen2.5-VL 72B", "ggml-org/Qwen2.5-VL-72B-Instruct-GGUF", "Qwen2.5-VL-72B-Instruct-Q4_K_M.gguf", 47.42,
                de ? "Das größte Vision-Modell hier – braucht ~54 GB Speicher." : "The largest vision model here - needs ~54 GB memory.", "mmproj-Qwen2.5-VL-72B-Instruct-Q8_0.gguf", 0.75));
            l.Add(Img("sd15", "Stable Diffusion 1.5", "Comfy-Org/stable-diffusion-v1-5-archive", "v1-5-pruned-emaonly-fp16.safetensors", 2.13, 4.0,
                de ? "Der Klassiker: schnell, geringer Speicherbedarf, vielseitig." : "The classic: fast, low memory use, versatile."));
            l.Add(Img("counterfeit3", "Counterfeit V3.0 (Anime)", "gsdf/Counterfeit-V3.0", "Counterfeit-V3.0_fp16.safetensors", 4.24, 5.5,
                de ? "Anime-Stil mit schönen Farben – passt gut zu Yume-Charakteren." : "Anime style with beautiful colors - fits Yume characters well."));
            l.Add(Img("animaginexl", "Animagine XL 3.1 (Anime)", "cagliostrolab/animagine-xl-3.1", "animagine-xl-3.1.safetensors", 6.94, 9.0,
                de ? "Beste Anime-Qualität (SDXL). Braucht viel Grafikspeicher oder Auslagerung." : "Best anime quality (SDXL). Needs a lot of graphics memory or offloading."));
            l.Add(Img("animaginexl4", "Animagine XL 4.0 (Anime)", "cagliostrolab/animagine-xl-4.0", "animagine-xl-4.0.safetensors", 6.94, 9.0,
                de ? "Neuere Animagine-Version mit noch besseren Details und Händen." : "Newer Animagine version with better details and hands."));
            l.Add(Img("sdxl", "Stable Diffusion XL 1.0", "stabilityai/stable-diffusion-xl-base-1.0", "sd_xl_base_1.0.safetensors", 6.94, 9.0,
                de ? "Hochauflösender Allrounder (1024 px): Landschaften, Szenen, Porträts." : "High-resolution all-rounder (1024 px): landscapes, scenes, portraits."));
            foreach (ModelInfo m in l)
                if (m.Id == "t-qwen3-14b" || m.Id == "t-qwen25-coder-7b" || m.Id == "qwen3-30b-a3b" || m.Id == "r1-14b" || m.Id == "r1-32b" || m.Id == "gptoss-20b" || m.Id == "phi4-14b" || m.Id == "gemma3-4b-q8") m.NoAuto = true;
            return l;
        }
    }

    class Hardware
    {
        public string GpuName = "";
        public double VramGb;
        public bool Nvidia, Discrete;
        public int DriverMajor;
        public double RamGb;
        public int Cores;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        class MEMORYSTATUSEX
        {
            public uint dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX));
            public uint dwMemoryLoad; public ulong ullTotalPhys, ullAvailPhys, ullTotalPageFile, ullAvailPageFile, ullTotalVirtual, ullAvailVirtual, ullAvailExtendedVirtual;
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        static extern bool GlobalMemoryStatusEx([In, Out] MEMORYSTATUSEX lpBuffer);

        public double UsableGb { get { return Discrete ? VramGb : Math.Max(0, RamGb * 0.55 - 2); } }

        public static Hardware Detect()
        {
            Hardware h = new Hardware();
            h.Cores = Environment.ProcessorCount;
            try { MEMORYSTATUSEX m = new MEMORYSTATUSEX(); if (GlobalMemoryStatusEx(m)) h.RamGb = m.ullTotalPhys / 1073741824.0; } catch { }
            // 1) NVIDIA: nvidia-smi gives exact numbers
            string smi = FindNvidiaSmi();
            if (smi != null)
            {
                try
                {
                    string o = Run(smi, "--query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits", 6000);
                    string first = o.Split('\n')[0].Trim();
                    string[] p = first.Split(',');
                    if (p.Length >= 3)
                    {
                        h.GpuName = p[0].Trim(); h.Nvidia = true; h.Discrete = true;
                        double mib; double.TryParse(p[1].Trim(), System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out mib);
                        h.VramGb = mib / 1024.0;
                        Match mm = Regex.Match(p[2].Trim(), "^(\\d+)");
                        if (mm.Success) h.DriverMajor = int.Parse(mm.Groups[1].Value);
                    }
                }
                catch { }
            }
            // 2) other GPUs: WMI name + exact VRAM from the registry (AdapterRAM is capped at 4 GB)
            if (!h.Nvidia)
            {
                try
                {
                    using (ManagementObjectSearcher s = new ManagementObjectSearcher("SELECT Name FROM Win32_VideoController"))
                        foreach (ManagementObject o in s.Get())
                        {
                            string n = Convert.ToString(o["Name"]);
                            if (string.IsNullOrEmpty(n) || n.IndexOf("Basic", StringComparison.OrdinalIgnoreCase) >= 0 || n.IndexOf("Remote", StringComparison.OrdinalIgnoreCase) >= 0 || n.IndexOf("Virtual", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                            double v = RegistryVram(n);
                            bool integrated = Regex.IsMatch(n, "UHD|Iris|Radeon\\(TM\\) Graphics|Radeon Graphics|Vega|Intel\\(R\\) HD", RegexOptions.IgnoreCase) && !Regex.IsMatch(n, "Arc", RegexOptions.IgnoreCase);
                            if (!integrated && v >= h.VramGb)
                            {
                                h.GpuName = n; h.VramGb = v; h.Discrete = true;
                            }
                            else if (h.GpuName.Length == 0)
                            {
                                h.GpuName = n; h.VramGb = v;
                            }
                        }
                }
                catch { }
            }
            return h;
        }

        static string FindNvidiaSmi()
        {
            string[] c = { Path.Combine(Environment.SystemDirectory, "nvidia-smi.exe"), @"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe" };
            foreach (string s in c) if (File.Exists(s)) return s;
            return null;
        }

        static double RegistryVram(string name)
        {
            try
            {
                using (RegistryKey cls = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"))
                {
                    if (cls == null) return 0;
                    foreach (string sub in cls.GetSubKeyNames())
                    {
                        if (!Regex.IsMatch(sub, "^\\d{4}$")) continue;
                        using (RegistryKey k = cls.OpenSubKey(sub))
                        {
                            if (k == null) continue;
                            string desc = Convert.ToString(k.GetValue("DriverDesc"));
                            if (desc != name) continue;
                            object v = k.GetValue("HardwareInformation.qwMemorySize");
                            if (v is long) return ((long)v) / 1073741824.0;
                            byte[] b = v as byte[];
                            if (b != null && b.Length >= 8) return BitConverter.ToInt64(b, 0) / 1073741824.0;
                        }
                    }
                }
            }
            catch { }
            return 0;
        }

        public static string Run(string exe, string args, int timeoutMs)
        {
            ProcessStartInfo psi = new ProcessStartInfo(exe, args);
            psi.RedirectStandardOutput = true; psi.UseShellExecute = false; psi.CreateNoWindow = true;
            using (Process p = Process.Start(psi))
            {
                string o = p.StandardOutput.ReadToEnd();
                p.WaitForExit(timeoutMs);
                return o;
            }
        }

        // 0 = does not fit, 1 = tight, 2 = fits well
        public int Fit(ModelInfo m)
        {
            double usable = UsableGb;
            if (!Discrete) return (m.SizeGb + m.MmprojGb) * 1.15 + 1.5 <= RamGb * 0.55 ? (m.SizeGb <= 3.0 ? 2 : 1) : 0;
            if (m.NeedGb <= usable) return 2;
            if ((m.SizeGb + m.MmprojGb) * 1.05 <= usable + RamGb * 0.15) return 1;
            return 0;
        }

        public ModelInfo Recommend(List<ModelInfo> models, string kind)
        {
            ModelInfo best = null;
            foreach (ModelInfo m in models)
            {
                if (m.Kind != kind || m.NoAuto) continue;   // MoE / reasoning / special models are never an automatic pick
                if (Fit(m) == 2) best = m;                    // list order = quality order: the last model that fits well wins
            }
            if (best == null) foreach (ModelInfo m in models) if (m.Kind == kind && (best == null || m.SizeGb < best.SizeGb)) best = m;
            return best;
        }

        public string Describe()
        {
            string ram = string.Format("{0:0} GB {1}", RamGb, Loc.T("ram"));
            if (GpuName.Length == 0) return Loc.T("nogpu") + "  ·  " + ram + "  ·  " + Cores + " CPU";
            if (Discrete) return string.Format("{0} ({1:0} GB VRAM)  ·  {2}  ·  {3} CPU", GpuName, VramGb, ram, Cores);
            return string.Format("{0}  ·  {1}  ·  {2} CPU  -  {3}", GpuName, ram, Cores, Loc.T("nogpu"));
        }
    }

    class AppSettings
    {
        static string Dir { get { return Paths.Root; } }
        public int Port = 8080, VisionPort = 8081, ImagePort = 8082, Ctx = 8192;
        public string ApiKey = "", Engine = "auto", ImageEngine = "auto", LlmId = "", VisionId = "", ImageId = "", ToolsId = "";
        public bool Lan = true, Autostart = false, AutoRun = false, FwAsked = false, LlmOn = true, VisionOn = false, ImageOn = false, ToolsOn = false;
        static string File_ { get { return Path.Combine(Dir, "settings.ini"); } }
        public static AppSettings Load()
        {
            AppSettings s = new AppSettings();
            try
            {
                if (File.Exists(File_))
                    foreach (string line in File.ReadAllLines(File_, Encoding.UTF8))
                    {
                        int i = line.IndexOf('=');
                        if (i <= 0) continue;
                        string k = line.Substring(0, i).Trim(), v = line.Substring(i + 1).Trim();
                        int n;
                        switch (k)
                        {
                            case "port": if (int.TryParse(v, out n)) s.Port = n; break;
                            case "vision_port": if (int.TryParse(v, out n)) s.VisionPort = n; break;
                            case "ctx": if (int.TryParse(v, out n)) s.Ctx = n; break;
                            case "image_port": if (int.TryParse(v, out n)) s.ImagePort = n; break;
                            case "api_key": s.ApiKey = v; break;
                            case "engine": s.Engine = v; break;
                            case "llm": s.LlmId = v; break;
                            case "vision": s.VisionId = v; break;
                            case "lan": s.Lan = v == "1"; break;
                            case "autostart": s.Autostart = v == "1"; break;
                            case "autorun": s.AutoRun = v == "1"; break;
                            case "fw_asked": s.FwAsked = v == "1"; break;
                            case "image_engine": s.ImageEngine = v; break;
                            case "image": s.ImageId = v; break;
                            case "llm_on": s.LlmOn = v == "1"; break;
                            case "vision_on": s.VisionOn = v == "1"; break;
                            case "image_on": s.ImageOn = v == "1"; break;
                            case "tools": s.ToolsId = v; break;
                            case "tools_on": s.ToolsOn = v == "1"; break;
                        }
                    }
            }
            catch { }
            return s;
        }
        public void Save()
        {
            try
            {
                Directory.CreateDirectory(Dir);
                File.WriteAllLines(File_, new[] {
                    "port=" + Port, "vision_port=" + VisionPort, "image_port=" + ImagePort, "ctx=" + Ctx, "api_key=" + ApiKey, "engine=" + Engine,
                    "llm=" + LlmId, "vision=" + VisionId, "lan=" + (Lan ? "1" : "0"), "autostart=" + (Autostart ? "1" : "0"), "autorun=" + (AutoRun ? "1" : "0"), "fw_asked=" + (FwAsked ? "1" : "0"), "image_engine=" + ImageEngine, "image=" + ImageId, "llm_on=" + (LlmOn ? "1" : "0"), "vision_on=" + (VisionOn ? "1" : "0"), "image_on=" + (ImageOn ? "1" : "0"), "tools=" + ToolsId, "tools_on=" + (ToolsOn ? "1" : "0") }, Encoding.UTF8);
            }
            catch { }
        }
    }

    static class Paths
    {
        public static string Root { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "YumeLLMServer"); } }
        public static string Models { get { return Path.Combine(Root, "models"); } }
        public static string Engine(string type) { return Path.Combine(Path.Combine(Root, "engine"), type); }
        public static string ImageEngine(string type) { return Path.Combine(Path.Combine(Path.Combine(Root, "engine"), "sd"), type); }
        public static string Log { get { return Path.Combine(Path.Combine(Root, "logs"), "server.log"); } }
    }

    // ------------------------------------------------------------------ downloads + engine
    static class Net
    {
        // Big files from huggingface.co regularly stall or drop in the middle: continue where the .part file ended, as long as it makes progress.
        public static void Download(string url, string dest, Action<long, long> progress, Func<bool> cancelled)
        {
            int fails = 0; long lastSize = -1;
            while (true)
            {
                try { DownloadOnce(url, dest, progress, cancelled); return; }
                catch (OperationCanceledException) { throw; }
                catch (Exception)
                {
                    string part = dest + ".part";
                    long size = File.Exists(part) ? new FileInfo(part).Length : 0;
                    if (size > lastSize) fails = 0; else fails++;
                    lastSize = size;
                    if (fails >= 6) throw;
                    for (int i = 0; i < 4 * (fails + 1); i++)
                    {
                        if (cancelled != null && cancelled()) throw new OperationCanceledException();
                        Thread.Sleep(500);
                    }
                }
            }
        }

        static void DownloadOnce(string url, string dest, Action<long, long> progress, Func<bool> cancelled)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            string part = dest + ".part";
            long have = File.Exists(part) ? new FileInfo(part).Length : 0;
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
            req.UserAgent = "YumeLLMServer/" + Program.Version;
            req.AllowAutoRedirect = true;
            req.Timeout = 30000; req.ReadWriteTimeout = 30000;
            if (have > 0) req.AddRange(have);
            HttpWebResponse resp;
            try { resp = (HttpWebResponse)req.GetResponse(); }
            catch (WebException ex)
            {
                HttpWebResponse r = ex.Response as HttpWebResponse;
                if (r != null && (int)r.StatusCode == 416 && have > 0) { if (File.Exists(dest)) File.Delete(dest); File.Move(part, dest); return; }
                throw;
            }
            using (resp)
            {
                bool partial = resp.StatusCode == HttpStatusCode.PartialContent;
                if (!partial) have = 0;
                long total = resp.ContentLength > 0 ? resp.ContentLength + have : -1;
                using (Stream s = resp.GetResponseStream())
                using (FileStream fs = new FileStream(part, partial ? FileMode.Append : FileMode.Create, FileAccess.Write))
                {
                    byte[] buf = new byte[256 * 1024];
                    long got = have;
                    DateTime last = DateTime.MinValue;
                    int n;
                    while ((n = s.Read(buf, 0, buf.Length)) > 0)
                    {
                        if (cancelled != null && cancelled()) throw new OperationCanceledException();
                        fs.Write(buf, 0, n);
                        got += n;
                        if (progress != null && (DateTime.UtcNow - last).TotalMilliseconds > 150) { progress(got, total); last = DateTime.UtcNow; }
                    }
                    if (progress != null) progress(got, total);
                }
            }
            if (File.Exists(dest)) File.Delete(dest);
            File.Move(part, dest);
        }

        public static string GetString(string url)
        {
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
            req.UserAgent = "YumeLLMServer/" + Program.Version;
            req.Timeout = 20000;
            using (WebResponse r = req.GetResponse())
            using (StreamReader sr = new StreamReader(r.GetResponseStream(), Encoding.UTF8)) return sr.ReadToEnd();
        }
    }

    static class Engine
    {
        const string PinnedTag = "b11715";

        public static string PickType(string setting, Hardware hw)
        {
            if (setting == "cuda" || setting == "vulkan" || setting == "cpu") return setting;
            if (hw.Nvidia) return "cuda";
            if (hw.Discrete) return "vulkan";
            return "cpu";
        }

        public static string ServerExe(string type)
        {
            string dir = Paths.Engine(type);
            if (!Directory.Exists(dir)) return null;
            string[] f = Directory.GetFiles(dir, "llama-server.exe", SearchOption.AllDirectories);
            return f.Length > 0 ? f[0] : null;
        }

        public static string InstalledVersion(string type)
        {
            try { string p = Path.Combine(Paths.Engine(type), "version.txt"); return File.Exists(p) ? File.ReadAllText(p).Trim() : ""; } catch { return ""; }
        }

        class Asset { public string Name, Url; }

        static List<Asset> Assets(out string tag)
        {
            tag = PinnedTag;
            List<Asset> list = new List<Asset>();
            try
            {
                string json = Net.GetString("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15");
                // pick the first release whose tag starts with "b" and read its assets (simple JSON scan, no external library)
                foreach (Match rel in Regex.Matches(json, "\"tag_name\"\\s*:\\s*\"(b\\d+)\""))
                {
                    tag = rel.Groups[1].Value;
                    int start = rel.Index;
                    int next = json.IndexOf("\"tag_name\"", start + 20, StringComparison.Ordinal);
                    string slice = next > 0 ? json.Substring(start, next - start) : json.Substring(start);
                    foreach (Match a in Regex.Matches(slice, "\"browser_download_url\"\\s*:\\s*\"([^\"]+\\.zip)\""))
                    {
                        string url = a.Groups[1].Value;
                        list.Add(new Asset { Url = url, Name = url.Substring(url.LastIndexOf('/') + 1) });
                    }
                    if (list.Count > 0) return list;
                }
            }
            catch { }
            tag = PinnedTag;
            string b = "https://github.com/ggml-org/llama.cpp/releases/download/" + PinnedTag + "/";
            foreach (string n in new[] { "llama-" + PinnedTag + "-bin-win-cpu-x64.zip", "llama-" + PinnedTag + "-bin-win-vulkan-x64.zip",
                "llama-" + PinnedTag + "-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip",
                "llama-" + PinnedTag + "-bin-win-cuda-13.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip" })
                list.Add(new Asset { Name = n, Url = b + n });
            return list;
        }

        public static void UnzipPublic(string zip, string dir) { Unzip(zip, dir); }

        static void Unzip(string zip, string dir)
        {
            using (ZipArchive za = ZipFile.OpenRead(zip))
                foreach (ZipArchiveEntry e in za.Entries)
                {
                    string path = Path.GetFullPath(Path.Combine(dir, e.FullName));
                    if (!path.StartsWith(Path.GetFullPath(dir), StringComparison.OrdinalIgnoreCase)) continue;      // no path traversal
                    if (e.FullName.EndsWith("/") || e.Name.Length == 0) { Directory.CreateDirectory(path); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    e.ExtractToFile(path, true);
                }
        }

        public static bool VcRuntimeMissing()
        {
            return !File.Exists(Path.Combine(Environment.SystemDirectory, "vcruntime140.dll")) || !File.Exists(Path.Combine(Environment.SystemDirectory, "msvcp140.dll"));
        }

        public static void EnsureVcRuntime(Action<string> status)
        {
            if (!VcRuntimeMissing()) return;
            status(Loc.T("vc"));
            string exe = Path.Combine(Path.GetTempPath(), "vc_redist.x64.exe");
            Net.Download("https://aka.ms/vs/17/release/vc_redist.x64.exe", exe, null, null);
            ProcessStartInfo psi = new ProcessStartInfo(exe, "/install /quiet /norestart");
            psi.Verb = "runas"; psi.UseShellExecute = true;
            using (Process p = Process.Start(psi)) p.WaitForExit(300000);
        }

        // Downloads + unpacks the engine for the given type. progress(0..1, text)
        public static void Install(string type, Hardware hw, Action<double, string> progress, Func<bool> cancelled)
        {
            string tag;
            List<Asset> assets = Assets(out tag);
            List<Asset> need = new List<Asset>();
            string cuda = hw.DriverMajor >= 580 ? "13.4" : "12.4";
            foreach (Asset a in assets)
            {
                string n = a.Name.ToLowerInvariant();
                if (n.Contains("arm64")) continue;
                if (type == "cpu" && n.StartsWith("llama-") && n.Contains("bin-win-cpu-x64")) need.Add(a);
                if (type == "vulkan" && n.StartsWith("llama-") && n.Contains("bin-win-vulkan-x64")) need.Add(a);
                if (type == "cuda" && n.Contains("bin-win-cuda-" + cuda + "-x64")) need.Add(a);
            }
            if (need.Count == 0) throw new Exception("No matching engine package found for '" + type + "'.");
            string dir = Paths.Engine(type);
            Directory.CreateDirectory(dir);
            string tmp = Path.Combine(Paths.Root, "downloads");
            Directory.CreateDirectory(tmp);
            for (int i = 0; i < need.Count; i++)
            {
                Asset a = need[i];
                string zip = Path.Combine(tmp, a.Name);
                int idx = i;
                Net.Download(a.Url, zip, delegate(long got, long total)
                {
                    double frac = total > 0 ? (double)got / total : 0;
                    progress((idx + frac * 0.9) / need.Count, string.Format("{0}  {1:0} / {2:0} MB", a.Name, got / 1048576.0, total > 0 ? total / 1048576.0 : 0));
                }, cancelled);
                progress((idx + 0.92) / need.Count, "Entpacken / Unpacking " + a.Name);
                Unzip(zip, dir);
                try { File.Delete(zip); } catch { }
            }
            File.WriteAllText(Path.Combine(dir, "version.txt"), tag);
        }
    }

    // stable-diffusion.cpp (sd-server): A1111-compatible image API, used by Yume Companion's image generation
    static class ImageEngine
    {
        const string PinnedTag = "master-973-f0aac52";

        public static string PickType(string setting, Hardware hw)
        {
            if (setting == "cuda" || setting == "vulkan" || setting == "cpu") return setting;
            return hw.Discrete ? "vulkan" : "cpu";          // Vulkan = small download and works on every GPU brand
        }

        public static string ServerExe(string type)
        {
            string dir = Paths.ImageEngine(type);
            if (!Directory.Exists(dir)) return null;
            string[] f = Directory.GetFiles(dir, "sd-server.exe", SearchOption.AllDirectories);
            return f.Length > 0 ? f[0] : null;
        }

        public static string InstalledVersion(string type)
        {
            try { string p = Path.Combine(Paths.ImageEngine(type), "version.txt"); return File.Exists(p) ? File.ReadAllText(p).Trim() : ""; } catch { return ""; }
        }

        static List<string[]> Assets(out string tag)       // {name, url}
        {
            tag = PinnedTag;
            List<string[]> list = new List<string[]>();
            try
            {
                string json = Net.GetString("https://api.github.com/repos/leejet/stable-diffusion.cpp/releases?per_page=10");
                foreach (Match rel in Regex.Matches(json, "\"tag_name\"\\s*:\\s*\"(master-[^\"]+)\""))
                {
                    int start = rel.Index;
                    int next = json.IndexOf("\"tag_name\"", start + 20, StringComparison.Ordinal);
                    string slice = next > 0 ? json.Substring(start, next - start) : json.Substring(start);
                    List<string[]> found = new List<string[]>();
                    foreach (Match a in Regex.Matches(slice, "\"browser_download_url\"\\s*:\\s*\"([^\"]+\\.zip)\""))
                    {
                        string url = a.Groups[1].Value;
                        found.Add(new[] { url.Substring(url.LastIndexOf('/') + 1), url });
                    }
                    if (found.Any(delegate(string[] x) { return x[0].Contains("bin-win-cpu-x64"); })) { tag = rel.Groups[1].Value; return found; }
                }
            }
            catch { }
            string b = "https://github.com/leejet/stable-diffusion.cpp/releases/download/" + PinnedTag + "/";
            foreach (string n in new[] { "sd-master-f0aac52-bin-win-cpu-x64.zip", "sd-master-f0aac52-bin-win-vulkan-x64.zip", "sd-master-f0aac52-bin-win-cuda12-x64.zip", "cudart-sd-bin-win-cu12-x64.zip" })
                list.Add(new[] { n, b + n });
            return list;
        }

        public static void Install(string type, Hardware hw, Action<double, string> progress, Func<bool> cancelled)
        {
            string tag;
            List<string[]> assets = Assets(out tag);
            List<string[]> need = new List<string[]>();
            foreach (string[] a in assets)
            {
                string n = a[0].ToLowerInvariant();
                if (type == "cpu" && n.Contains("bin-win-cpu-x64")) need.Add(a);
                if (type == "vulkan" && n.Contains("bin-win-vulkan-x64")) need.Add(a);
                if (type == "cuda" && (n.Contains("bin-win-cuda12-x64") || n.StartsWith("cudart-sd-bin-win-cu12"))) need.Add(a);
            }
            if (need.Count == 0) throw new Exception("No matching image engine package found for '" + type + "'.");
            string dir = Paths.ImageEngine(type);
            Directory.CreateDirectory(dir);
            string tmp = Path.Combine(Paths.Root, "downloads");
            Directory.CreateDirectory(tmp);
            for (int i = 0; i < need.Count; i++)
            {
                string name = need[i][0], url = need[i][1];
                string zip = Path.Combine(tmp, name);
                int idx = i;
                Net.Download(url, zip, delegate(long got, long total)
                {
                    double frac = total > 0 ? (double)got / total : 0;
                    progress((idx + frac * 0.9) / need.Count, string.Format("{0}  {1:0} / {2:0} MB", name, got / 1048576.0, total > 0 ? total / 1048576.0 : 0));
                }, cancelled);
                progress((idx + 0.92) / need.Count, "Entpacken / Unpacking " + name);
                Engine.UnzipPublic(zip, dir);
                try { File.Delete(zip); } catch { }
            }
            File.WriteAllText(Path.Combine(dir, "version.txt"), tag);
        }
    }

    // ------------------------------------------------------------------ server processes
    class ServerRunner
    {
        public Process Llm, Vision, Image, Tools;
        public event Action<string> LogLine;
        public event Action Changed;
        public bool LlmReady, VisionReady, ImageReady, ToolsReady;
        readonly object logLock = new object();
        string argsKeyMask = "\u0001";

        public bool Running { get { return (Llm != null && !Llm.HasExited) || (Vision != null && !Vision.HasExited) || (Image != null && !Image.HasExited) || (Tools != null && !Tools.HasExited); } }

        void Log(string s)
        {
            try { lock (logLock) { Directory.CreateDirectory(Path.GetDirectoryName(Paths.Log)); File.AppendAllText(Paths.Log, s + Environment.NewLine); } } catch { }
            Action<string> h = LogLine; if (h != null) h(s);
        }

        Process Launch(string exe, string args, string tag)
        {
            ProcessStartInfo psi = new ProcessStartInfo(exe, args);
            psi.UseShellExecute = false; psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true; psi.RedirectStandardError = true;
            psi.WorkingDirectory = Path.GetDirectoryName(exe);
            Process p = new Process(); p.StartInfo = psi; p.EnableRaisingEvents = true;
            p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) Log("[" + tag + "] " + e.Data); };
            p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) Log("[" + tag + "] " + e.Data); };
            p.Exited += delegate { Action h = Changed; if (h != null) h(); };
            Log("> " + exe + " " + args.Replace(argsKeyMask, "***"));
            p.Start(); p.BeginOutputReadLine(); p.BeginErrorReadLine();
            return p;
        }

        public void Start(string exe, bool gpu, AppSettings s, ModelInfo llm, ModelInfo vision, ModelInfo image, string sdExe, bool sdOffload, ModelInfo tools = null)
        {
            Stop();
            LlmReady = VisionReady = ImageReady = ToolsReady = false;
            string host = s.Lan ? "0.0.0.0" : "127.0.0.1";
            string key = s.ApiKey.Length > 0 ? " --api-key \"" + s.ApiKey + "\"" : "";
            argsKeyMask = s.ApiKey.Length > 0 ? s.ApiKey : "\u0001";
            string ngl = "";                                   // default -ngl auto + --fit on: the engine moves layers to RAM if the model is too big for the GPU
            if (llm != null && exe != null)
                Llm = Launch(exe, "-m \"" + Path.Combine(Paths.Models, llm.File) + "\" --host " + host + " --port " + s.Port + " -c " + s.Ctx + " --parallel 1" + ngl + " --jinja" + key, "LLM");
            if (vision != null && exe != null)
                Vision = Launch(exe, "-m \"" + Path.Combine(Paths.Models, vision.File) + "\" --mmproj \"" + Path.Combine(Paths.Models, vision.Mmproj) + "\" --host " + host +
                    " --port " + (s.Port + 1) + " -c 4096 --parallel 1" + ngl + " --jinja" + key, "VISION");
            if (tools != null && exe != null)                  // second language model only for tool calls (own port: Port + 3)
                Tools = Launch(exe, "-m \"" + Path.Combine(Paths.Models, tools.File) + "\" --host " + host + " --port " + (s.Port + 3) + " -c " + s.Ctx + " --parallel 1" + ngl + " --jinja" + key, "TOOLS");
            if (image != null && sdExe != null)
                Image = Launch(sdExe, "-m \"" + Path.Combine(Paths.Models, image.File) + "\" -l " + host + " --listen-port " + (s.Port + 2) + (sdOffload ? " --offload-to-cpu" : ""), "IMAGE");
            Thread t = new Thread(delegate()
            {
                int guard = 0;
                while (Running && guard++ < 900)
                {
                    if (Llm != null && !Llm.HasExited && !LlmReady) LlmReady = Health(s.Port, "/health");
                    if (Vision != null && !Vision.HasExited && !VisionReady) VisionReady = Health(s.Port + 1, "/health");
                    if (Image != null && !Image.HasExited && !ImageReady) ImageReady = Health(s.Port + 2, "/sdapi/v1/options");
                    if (Tools != null && !Tools.HasExited && !ToolsReady) ToolsReady = Health(s.Port + 3, "/health");
                    Action h = Changed; if (h != null) h();
                    if ((Llm == null || Llm.HasExited || LlmReady) && (Vision == null || Vision.HasExited || VisionReady) && (Image == null || Image.HasExited || ImageReady) && (Tools == null || Tools.HasExited || ToolsReady)) break;
                    Thread.Sleep(1000);
                }
            });
            t.IsBackground = true; t.Start();
        }

        static bool Health(int port, string path)
        {
            try
            {
                HttpWebRequest r = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + path);
                r.Timeout = 1500;
                using (HttpWebResponse resp = (HttpWebResponse)r.GetResponse()) return (int)resp.StatusCode == 200;
            }
            catch (WebException ex) { return path != "/health" && ex.Response != null; }   // image server: any HTTP answer means it is up
            catch { return false; }
        }

        public void Stop()
        {
            foreach (Process p in new[] { Llm, Vision, Image, Tools })
            {
                try { if (p != null && !p.HasExited) { p.Kill(); p.WaitForExit(3000); } } catch { }
            }
            Llm = Vision = Image = Tools = null; LlmReady = VisionReady = ImageReady = ToolsReady = false;
            Action h = Changed; if (h != null) h();
        }
    }

    // ------------------------------------------------------------------ model card
    class ModelCard : Panel
    {
        public ModelInfo Model;
        public int Fit;                     // 0/1/2
        public bool Recommended, Installed, Active, Busy;
        public double Progress;
        public string Status = "";
        public RoundButton BtnMain, BtnDelete;
        public SlimProgress Bar;
        public Action<ModelCard> OnMain, OnDelete;

        public ModelCard(ModelInfo m)
        {
            Model = m;
            DoubleBuffered = true; Height = 84; BackColor = Theme.Bg;
            BtnMain = new RoundButton(); BtnMain.Width = 140; BtnMain.Height = 34;
            BtnDelete = new RoundButton(); BtnDelete.Primary = false; BtnDelete.Width = 140; BtnDelete.Height = 24; BtnDelete.Font = Theme.F(8f, FontStyle.Regular);
            Bar = new SlimProgress(); Bar.Visible = false;
            Controls.Add(BtnMain); Controls.Add(BtnDelete); Controls.Add(Bar);
            BtnMain.Click += delegate { if (OnMain != null) OnMain(this); };
            BtnDelete.Click += delegate { if (OnDelete != null) OnDelete(this); };
            Resize += delegate { Layout_(); };
        }

        void Layout_()
        {
            BtnMain.Location = new Point(Width - BtnMain.Width - 16, 12);
            BtnDelete.Location = new Point(Width - BtnDelete.Width - 16, 50);
            Bar.Location = new Point(18, 56); Bar.Width = Math.Max(120, Width - 18 - BtnMain.Width - 40);
        }

        public void Refresh_()
        {
            Layout_();
            if (Busy)
            {
                BtnMain.Text = Loc.T("cancel"); BtnMain.Primary = false; BtnMain.Selected = false;
                Bar.Visible = true; Bar.Value = Progress; BtnDelete.Visible = false;
            }
            else
            {
                Bar.Visible = false;
                if (!Installed) { BtnMain.Text = Loc.T("download"); BtnMain.Primary = true; BtnMain.Selected = false; BtnDelete.Visible = false; }
                else
                {
                    BtnMain.Text = Active ? Loc.T("active") : Loc.T("select"); BtnMain.Primary = !Active; BtnMain.Selected = Active;
                    BtnDelete.Text = Loc.T("remove"); BtnDelete.Visible = true;
                }
            }
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
            Rectangle r = new Rectangle(1, 1, Width - 3, Height - 3);
            using (GraphicsPath p = Theme.Round(r, 14))
            {
                using (SolidBrush b = new SolidBrush(Active ? Color.FromArgb(40, 255, 143, 199) : Theme.Panel)) g.FillPath(b, p);
                using (Pen pen = new Pen(Active ? Theme.Pink : Theme.Line, Active ? 2f : 1f)) g.DrawPath(pen, p);
            }
            Font nameFont = Theme.F(11.5f, FontStyle.Bold);
            TextRenderer.DrawText(g, Model.Name, nameFont, new Point(18, 10), Theme.Text);
            string badge; Color bc;
            if (Recommended) { badge = Loc.T("rec"); bc = Theme.Pink2; }
            else if (Fit == 2) { badge = Loc.T("fits"); bc = Theme.Ok; }
            else if (Fit == 1) { badge = Loc.T("tight"); bc = Theme.Warn; }
            else { badge = Loc.T("toobig"); bc = Theme.Bad; }
            Size ns = TextRenderer.MeasureText(g, Model.Name, nameFont);
            TextRenderer.DrawText(g, badge, Theme.F(8.5f, FontStyle.Bold), new Point(18 + ns.Width + 12, 14), bc);
            if (Busy)
            {
                TextRenderer.DrawText(g, Status, Theme.F(8.5f, FontStyle.Regular), new Point(18, 34), Theme.Lav);
                return;
            }
            Rectangle dr = new Rectangle(18, 36, Width - 18 - 170, 20);
            TextRenderer.DrawText(g, Model.Desc, Theme.F(9f, FontStyle.Regular), dr, Theme.Muted, TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding | TextFormatFlags.SingleLine);
            string meta = string.Format("{0:0.0} GB   ·   {1}", Model.SizeGb + Model.MmprojGb, Loc.F("vram_need", Model.NeedGb));
            TextRenderer.DrawText(g, meta, Theme.F(8.5f, FontStyle.Regular), new Point(18, 58), Color.FromArgb(150, Theme.Lav));
        }
    }

    // ------------------------------------------------------------------ log window
    class LogForm : Form
    {
        TextBox box;
        public LogForm()
        {
            Text = "Yume LLM Server - " + Loc.T("log");
            BackColor = Theme.Bg; ClientSize = new Size(820, 480); StartPosition = FormStartPosition.CenterParent;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            box = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false, Dock = DockStyle.Fill, BackColor = Color.FromArgb(14, 10, 22), ForeColor = Theme.Muted, Font = new Font("Consolas", 9f), BorderStyle = BorderStyle.None };
            Controls.Add(box);
            Load += delegate { Reload(); };
        }
        public void Reload()
        {
            try
            {
                string text = File.Exists(Paths.Log) ? File.ReadAllText(Paths.Log) : "";
                if (text.Length > 80000) text = text.Substring(text.Length - 80000);
                box.Text = text; box.SelectionStart = box.TextLength; box.ScrollToCaret();
            }
            catch { }
        }
    }

    // ------------------------------------------------------------------ settings window (everything that is not needed every day)
    class SettingsForm : Form
    {
        readonly AppSettings cfg;
        readonly MainForm owner;
        NumericUpDown numPort;
        ComboBox cbCtx, cbEngLlm, cbEngImg;
        TextBox txtKey;
        CheckBox chkLan, chkAuto, chkRun;

        static Label L(string text, int x, int y, bool bold)
        {
            return new Label { Text = text, UseMnemonic = false, AutoSize = true, Location = new Point(x, y), ForeColor = bold ? Theme.Lav : Theme.Muted, Font = bold ? Theme.F(8.5f, FontStyle.Bold) : Theme.F(9f, FontStyle.Regular), BackColor = Color.Transparent };
        }

        public SettingsForm(AppSettings cfg, MainForm owner)
        {
            this.cfg = cfg; this.owner = owner;
            Text = Loc.T("settings");
            BackColor = Theme.Bg; ForeColor = Theme.Text; Font = Theme.F(9f, FontStyle.Regular);
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false;
            ClientSize = new Size(560, 560); StartPosition = FormStartPosition.CenterParent;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            int y = 16;
            Controls.Add(L(Loc.T("s_net"), 20, y, true)); y += 26;
            Controls.Add(L(Loc.T("port"), 20, y + 4, false));
            numPort = new NumericUpDown { Minimum = 1024, Maximum = 65000, Width = 90, Location = new Point(70, y), BackColor = Theme.Panel2, ForeColor = Theme.Text, BorderStyle = BorderStyle.FixedSingle };
            Controls.Add(numPort);
            Controls.Add(L(Loc.T("port_hint"), 175, y + 4, false)); y += 36;
            Controls.Add(L(Loc.T("key"), 20, y + 4, false));
            txtKey = new TextBox { Width = 260, Location = new Point(230, y), UseSystemPasswordChar = true, BackColor = Theme.Panel2, ForeColor = Theme.Text, BorderStyle = BorderStyle.FixedSingle };
            Controls.Add(txtKey); y += 34;
            chkLan = new CheckBox { Text = Loc.T("lan"), AutoSize = true, Location = new Point(20, y), ForeColor = Theme.Text, BackColor = Color.Transparent };
            Controls.Add(chkLan); y += 36;

            Controls.Add(L(Loc.T("s_perf"), 20, y, true)); y += 26;
            Controls.Add(L(Loc.T("ctx"), 20, y + 4, false));
            cbCtx = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 100, Location = new Point(230, y), FlatStyle = FlatStyle.Flat, BackColor = Theme.Panel2, ForeColor = Theme.Text };
            cbCtx.Items.AddRange(new object[] { "4096", "8192", "16384", "32768" });
            Controls.Add(cbCtx); y += 36;

            Controls.Add(L(Loc.T("s_engine"), 20, y, true)); y += 26;
            Controls.Add(L(Loc.T("eng_llm"), 20, y + 4, false));
            cbEngLlm = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200, Location = new Point(230, y), FlatStyle = FlatStyle.Flat, BackColor = Theme.Panel2, ForeColor = Theme.Text };
            cbEngLlm.Items.AddRange(new object[] { Loc.T("engine_auto"), "CUDA (NVIDIA)", "Vulkan", "CPU" });
            RoundButton bUpdLlm = new RoundButton { Text = Loc.T("update_short"), Primary = false, Width = 110, Height = 28, Location = new Point(440, y - 1), Font = Theme.F(8.5f, FontStyle.Bold) };
            Controls.Add(cbEngLlm); Controls.Add(bUpdLlm); y += 38;
            Controls.Add(L(Loc.T("eng_img"), 20, y + 4, false));
            cbEngImg = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200, Location = new Point(230, y), FlatStyle = FlatStyle.Flat, BackColor = Theme.Panel2, ForeColor = Theme.Text };
            cbEngImg.Items.AddRange(new object[] { Loc.T("engine_auto") + " (Vulkan)", "CUDA (NVIDIA)", "Vulkan", "CPU" });
            RoundButton bUpdImg = new RoundButton { Text = Loc.T("update_short"), Primary = false, Width = 110, Height = 28, Location = new Point(440, y - 1), Font = Theme.F(8.5f, FontStyle.Bold) };
            Controls.Add(cbEngImg); Controls.Add(bUpdImg); y += 40;

            Controls.Add(L(Loc.T("s_win"), 20, y, true)); y += 26;
            chkAuto = new CheckBox { Text = Loc.T("autostart"), AutoSize = true, Location = new Point(20, y), ForeColor = Theme.Text, BackColor = Color.Transparent };
            Controls.Add(chkAuto); y += 26;
            chkRun = new CheckBox { Text = Loc.T("autorun"), AutoSize = true, Location = new Point(20, y), ForeColor = Theme.Text, BackColor = Color.Transparent };
            Controls.Add(chkRun); y += 40;

            RoundButton bFw = new RoundButton { Text = Loc.T("firewall"), Primary = false, Width = 150, Height = 32, Location = new Point(20, y) };
            RoundButton bLog = new RoundButton { Text = Loc.T("log"), Primary = false, Width = 120, Height = 32, Location = new Point(182, y) };
            RoundButton bDir = new RoundButton { Text = Loc.T("open_models"), Primary = false, Width = 170, Height = 32, Location = new Point(314, y) };
            RoundButton bOk = new RoundButton { Text = "OK", Width = 100, Height = 32, Location = new Point(460, ClientSize.Height - 48) };
            Controls.AddRange(new Control[] { bFw, bLog, bDir, bOk });

            numPort.Value = Math.Max(numPort.Minimum, Math.Min(numPort.Maximum, cfg.Port));
            txtKey.Text = cfg.ApiKey; chkLan.Checked = cfg.Lan; chkAuto.Checked = cfg.Autostart; chkRun.Checked = cfg.AutoRun;
            cbCtx.SelectedItem = cfg.Ctx.ToString(); if (cbCtx.SelectedIndex < 0) cbCtx.SelectedItem = "8192";
            string[] keys = { "auto", "cuda", "vulkan", "cpu" };
            cbEngLlm.SelectedIndex = Math.Max(0, Array.IndexOf(keys, cfg.Engine));
            cbEngImg.SelectedIndex = Math.Max(0, Array.IndexOf(keys, cfg.ImageEngine));

            numPort.ValueChanged += delegate { cfg.Port = (int)numPort.Value; cfg.VisionPort = cfg.Port + 1; cfg.ImagePort = cfg.Port + 2; cfg.Save(); };
            txtKey.TextChanged += delegate { cfg.ApiKey = txtKey.Text.Trim(); cfg.Save(); };
            chkLan.CheckedChanged += delegate { cfg.Lan = chkLan.Checked; cfg.Save(); };
            cbCtx.SelectedIndexChanged += delegate { int c; if (int.TryParse(Convert.ToString(cbCtx.SelectedItem), out c)) { cfg.Ctx = c; cfg.Save(); } };
            cbEngLlm.SelectedIndexChanged += delegate { cfg.Engine = keys[Math.Max(0, cbEngLlm.SelectedIndex)]; cfg.Save(); };
            cbEngImg.SelectedIndexChanged += delegate { cfg.ImageEngine = keys[Math.Max(0, cbEngImg.SelectedIndex)]; cfg.Save(); };
            chkAuto.CheckedChanged += delegate { cfg.Autostart = chkAuto.Checked; cfg.Save(); MainForm.SetAutostart(chkAuto.Checked); };
            chkRun.CheckedChanged += delegate { cfg.AutoRun = chkRun.Checked; cfg.Save(); };
            bUpdLlm.Click += delegate { Close(); owner.InstallFamily("llama", null); };
            bUpdImg.Click += delegate { Close(); owner.InstallFamily("sd", null); };
            bFw.Click += delegate { owner.OpenFirewall(); };
            bLog.Click += delegate { new LogForm().ShowDialog(this); };
            bDir.Click += delegate { try { Directory.CreateDirectory(Paths.Models); Process.Start("explorer.exe", Paths.Models); } catch { } };
            bOk.Click += delegate { Close(); };
        }
    }

    // ------------------------------------------------------------------ main window
    class MainForm : Form
    {
        AppSettings cfg = AppSettings.Load();
        Hardware hw = new Hardware();
        List<ModelInfo> models = Catalog.All();
        ServerRunner runner = new ServerRunner();
        string kind = "llm";
        bool showAll = true, exiting, startMinimized, autoSetup, installing;
        readonly Dictionary<string, ModelCard> cards = new Dictionary<string, ModelCard>();
        readonly Dictionary<string, bool> cancelFlags = new Dictionary<string, bool>();
        EventWaitHandle exitEvent;

        Label lblTitle, lblSub, lblStatus, lblHw, lblEngineStatus, lblAddr, lblHint;
        RoundButton btnStart, btnTabLlm, btnTabVision, btnTabImage, btnTabTools, btnEngine, btnCopy, btnSettings, btnAll;
        CheckBox chkOn;
        Card strip, bottom;
        SlimProgress engineBar;
        Panel listPanel, header;
        NotifyIcon tray;
        System.Windows.Forms.Timer uiTimer;
        Label emptyNote;

        public MainForm(string[] args)
        {
            startMinimized = args.Any(delegate(string a) { return a == "--minimized"; });
            autoSetup = args.Any(delegate(string a) { return a == "--setup"; });
            foreach (string a in args) { if (a == "--tab=vision" || a == "--tab=image") kind = a.Substring(6); }
            try
            {
                exitEvent = new EventWaitHandle(false, EventResetMode.AutoReset, "Global\\YumeLlmServerExit");
                Thread w = new Thread(delegate() { exitEvent.WaitOne(); SafeInvoke(delegate { exiting = true; Close(); }); });
                w.IsBackground = true; w.Start();
            }
            catch { }
            Text = "Yume LLM Server";
            BackColor = Theme.Bg; ForeColor = Theme.Text; Font = Theme.F(9f, FontStyle.Regular);
            ClientSize = new Size(940, 680); MinimumSize = new Size(820, 600);
            StartPosition = FormStartPosition.CenterScreen;
            DoubleBuffered = true;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            BuildUi();
            BuildTray();
            runner.Changed += delegate { SafeInvoke(UpdateServerUi); };
            Load += delegate { OnLoaded(); };
            FormClosing += OnClosing;
            Resize += delegate { if (WindowState == FormWindowState.Minimized && runner.Running) Hide(); };
        }

        // ---------- UI construction
        void BuildUi()
        {
            header = new Panel { Dock = DockStyle.Top, Height = 84, BackColor = Theme.Bg };
            header.Paint += delegate(object s, PaintEventArgs e)
            {
                using (LinearGradientBrush b = new LinearGradientBrush(new Rectangle(0, 0, header.Width, 3), Theme.Pink, Theme.Lav, 0f)) e.Graphics.FillRectangle(b, 0, 0, header.Width, 3);
            };
            lblTitle = new Label { Text = "Yume LLM Server", Font = Theme.F(20f, FontStyle.Bold), ForeColor = Theme.Pink2, AutoSize = true, Location = new Point(24, 10), BackColor = Color.Transparent };
            lblSub = new Label { Text = Loc.T("subtitle"), Font = Theme.F(9.5f, FontStyle.Regular), ForeColor = Theme.Muted, AutoSize = true, Location = new Point(27, 50), BackColor = Color.Transparent };
            btnStart = new RoundButton { Text = Loc.T("start"), Width = 200, Height = 46, Font = Theme.F(11f, FontStyle.Bold) };
            lblStatus = new Label { Text = Loc.T("stopped"), Font = Theme.F(10f, FontStyle.Bold), ForeColor = Theme.Muted, AutoSize = false, TextAlign = ContentAlignment.MiddleRight, Width = 300, Height = 24, BackColor = Color.Transparent };
            header.Controls.AddRange(new Control[] { lblTitle, lblSub, btnStart, lblStatus });
            header.Resize += delegate { btnStart.Location = new Point(header.Width - btnStart.Width - 24, 20); lblStatus.Location = new Point(btnStart.Left - lblStatus.Width - 14, 31); };
            btnStart.Click += delegate { ToggleServer(); };

            // one calm line: the PC and the engine state
            strip = new Card { Height = 52 };
            lblHw = new Label { UseMnemonic = false, AutoSize = false, Font = Theme.F(10f, FontStyle.Bold), ForeColor = Theme.Text, Location = new Point(16, 8), Height = 20, BackColor = Color.Transparent };
            lblEngineStatus = new Label { UseMnemonic = false, AutoSize = false, Font = Theme.F(8.5f, FontStyle.Regular), ForeColor = Theme.Muted, Location = new Point(16, 29), Height = 18, BackColor = Color.Transparent };
            btnEngine = new RoundButton { Width = 190, Height = 30, Visible = false };
            engineBar = new SlimProgress { Visible = false, Height = 8 };
            strip.Controls.AddRange(new Control[] { lblHw, lblEngineStatus, btnEngine, engineBar });
            strip.Resize += delegate
            {
                lblHw.Width = strip.Width - 230; lblEngineStatus.Width = strip.Width - 230;
                btnEngine.Location = new Point(strip.Width - btnEngine.Width - 14, 11);
                engineBar.Location = new Point(16, strip.Height - 12); engineBar.Width = strip.Width - 32;
            };
            btnEngine.Click += delegate { InstallFamily(FamilyOf(kind), null); };

            btnTabLlm = new RoundButton { Text = Loc.T("tab_llm"), Width = 150, Height = 34 };
            btnTabVision = new RoundButton { Text = Loc.T("tab_vision"), Width = 150, Height = 34 };
            btnTabImage = new RoundButton { Text = Loc.T("tab_image"), Width = 150, Height = 34 };
            btnTabTools = new RoundButton { Text = Loc.T("tab_tools"), Width = 150, Height = 34 };
            btnSettings = new RoundButton { Text = "⚙  " + Loc.T("settings"), Primary = false, Width = 150, Height = 34 };
            btnTabLlm.Click += delegate { SetKind("llm"); };
            btnTabVision.Click += delegate { SetKind("vision"); };
            btnTabImage.Click += delegate { SetKind("image"); };
            btnTabTools.Click += delegate { SetKind("tools"); };
            btnSettings.Click += delegate { new SettingsForm(cfg, this).ShowDialog(this); UpdateAddress(); UpdateEngineUi(); };

            chkOn = new CheckBox { AutoSize = true, ForeColor = Theme.Text, BackColor = Color.Transparent, Font = Theme.F(9f, FontStyle.Regular) };
            btnAll = new RoundButton { Primary = false, Width = 220, Height = 28, Font = Theme.F(8.5f, FontStyle.Regular) };
            chkOn.CheckedChanged += delegate { if (loadingUi) return; SetOn(kind, chkOn.Checked); };
            btnAll.Click += delegate { showAll = !showAll; BuildCards(); };

            listPanel = new Panel { AutoScroll = true, BackColor = Theme.Bg };
            emptyNote = new Label { UseMnemonic = false, AutoSize = false, ForeColor = Theme.Muted, BackColor = Color.Transparent, Height = 24, Visible = false };

            bottom = new Card { Height = 70 };
            lblAddr = new Label { UseMnemonic = false, AutoSize = false, Font = Theme.F(12.5f, FontStyle.Bold), ForeColor = Theme.Pink2, Location = new Point(16, 8), Height = 26, BackColor = Color.Transparent };
            lblHint = new Label { UseMnemonic = false, AutoSize = false, Font = Theme.F(8.5f, FontStyle.Regular), ForeColor = Theme.Muted, Location = new Point(16, 38), Height = 20, BackColor = Color.Transparent };
            btnCopy = new RoundButton { Text = Loc.T("copy"), Primary = false, Width = 110, Height = 30 };
            bottom.Controls.AddRange(new Control[] { lblAddr, lblHint, btnCopy });
            bottom.Resize += delegate { lblAddr.Width = bottom.Width - 160; lblHint.Width = bottom.Width - 32; btnCopy.Location = new Point(bottom.Width - btnCopy.Width - 14, 10); };
            btnCopy.Click += delegate { Clipboard.SetText(CurrentUrl()); btnCopy.Text = Loc.T("copied"); };

            Controls.Add(listPanel); Controls.Add(emptyNote); Controls.Add(bottom); Controls.Add(chkOn); Controls.Add(btnAll);
            Controls.Add(btnTabLlm); Controls.Add(btnTabVision); Controls.Add(btnTabImage); Controls.Add(btnTabTools); Controls.Add(btnSettings); Controls.Add(strip); Controls.Add(header);
            Resize += delegate { LayoutAll(); }; LayoutAll();

            uiTimer = new System.Windows.Forms.Timer { Interval = 1500 };
            uiTimer.Tick += delegate { UpdateServerUi(); };
            uiTimer.Start();
        }

        bool loadingUi;

        void LayoutAll()
        {
            int w = ClientSize.Width, m = 22;
            strip.Location = new Point(m, 96); strip.Width = w - 2 * m;
            int ty = 160;
            btnTabLlm.Location = new Point(m, ty); btnTabVision.Location = new Point(m + 156, ty); btnTabImage.Location = new Point(m + 312, ty); btnTabTools.Location = new Point(m + 468, ty);
            btnSettings.Location = new Point(w - m - btnSettings.Width, ty);
            chkOn.Location = new Point(m + 4, ty + 46); btnAll.Location = new Point(w - m - btnAll.Width, ty + 42);
            bottom.Width = w - 2 * m; bottom.Location = new Point(m, ClientSize.Height - bottom.Height - 18);
            int top = ty + 78;
            listPanel.Location = new Point(m, top); listPanel.Size = new Size(w - 2 * m, Math.Max(100, bottom.Top - 10 - top));
            emptyNote.Location = new Point(m + 6, top + 6); emptyNote.Width = w - 2 * m;
            foreach (ModelCard c in cards.Values) c.Width = listPanel.ClientSize.Width - 4;
        }

        void BuildTray()
        {
            tray = new NotifyIcon { Icon = Icon ?? SystemIcons.Application, Text = "Yume LLM Server", Visible = true };
            ContextMenuStrip mn = new ContextMenuStrip();
            mn.Items.Add(Loc.T("tray_open"), null, delegate { ShowFromTray(); });
            mn.Items.Add(Loc.T("start") + " / " + Loc.T("stop"), null, delegate { ToggleServer(); });
            mn.Items.Add(Loc.T("tray_quit"), null, delegate { exiting = true; Close(); });
            tray.ContextMenuStrip = mn;
            tray.DoubleClick += delegate { ShowFromTray(); };
        }

        void ShowFromTray() { Show(); WindowState = FormWindowState.Normal; Activate(); }

        void OnClosing(object sender, FormClosingEventArgs e)
        {
            if (!exiting && runner.Running && e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true; Hide();
                tray.ShowBalloonTip(3000, "Yume LLM Server", Loc.T("tray_run"), ToolTipIcon.Info);
                return;
            }
            runner.Stop(); tray.Visible = false; tray.Dispose();
        }

        // ---------- helpers
        public void SafeInvoke(Action a)
        {
            try { if (IsHandleCreated && !IsDisposed) BeginInvoke(a); } catch { }
        }

        public static string LocalIp()
        {
            foreach (string target in new[] { "10.255.255.255", "8.8.8.8" })
            {
                try
                {
                    using (Socket s = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp))
                    {
                        s.Connect(target, 1);
                        string ip = ((IPEndPoint)s.LocalEndPoint).Address.ToString();
                        if (!ip.StartsWith("127.") && !ip.StartsWith("169.254.")) return ip;
                    }
                }
                catch { }
            }
            return "127.0.0.1";
        }

        static string FamilyOf(string k) { return k == "image" ? "sd" : "llama"; }
        int PortOf(string k) { return k == "llm" ? cfg.Port : k == "vision" ? cfg.Port + 1 : k == "tools" ? cfg.Port + 3 : cfg.Port + 2; }
        string UrlFor(string k) { return "http://" + (cfg.Lan ? LocalIp() : "127.0.0.1") + ":" + PortOf(k); }
        string CurrentUrl() { return UrlFor(kind); }

        bool IsOn(string k) { return k == "llm" ? cfg.LlmOn : k == "vision" ? cfg.VisionOn : k == "tools" ? cfg.ToolsOn : cfg.ImageOn; }
        void SetOn(string k, bool v) { if (k == "llm") cfg.LlmOn = v; else if (k == "vision") cfg.VisionOn = v; else if (k == "tools") cfg.ToolsOn = v; else cfg.ImageOn = v; cfg.Save(); }
        string SelectedId(string k) { return k == "llm" ? cfg.LlmId : k == "vision" ? cfg.VisionId : k == "tools" ? cfg.ToolsId : cfg.ImageId; }
        void SetSelected(string k, string id) { if (k == "llm") cfg.LlmId = id; else if (k == "vision") cfg.VisionId = id; else if (k == "tools") cfg.ToolsId = id; else cfg.ImageId = id; cfg.Save(); }

        ModelInfo Selected(string k)
        {
            string id = SelectedId(k);
            return models.FirstOrDefault(delegate(ModelInfo m) { return m.Id == id && m.Kind == k; });
        }

        bool IsInstalled(ModelInfo m)
        {
            if (!File.Exists(Path.Combine(Paths.Models, m.File))) return false;
            return m.Mmproj == null || File.Exists(Path.Combine(Paths.Models, m.Mmproj));
        }

        string EngineTypeFor(string family)
        {
            return family == "sd" ? ImageEngine.PickType(cfg.ImageEngine, hw) : Engine.PickType(cfg.Engine, hw);
        }

        string ExeFor(string family)
        {
            string t = EngineTypeFor(family);
            return family == "sd" ? ImageEngine.ServerExe(t) : Engine.ServerExe(t);
        }

        void SetKind(string k) { kind = k; BuildCards(); UpdateEngineUi(); UpdateAddress(); }

        void UpdateAddress()
        {
            lblAddr.Text = CurrentUrl();
            btnCopy.Text = Loc.T("copy");
            lblHint.Text = Loc.T(kind == "llm" ? "hint_llm" : kind == "vision" ? "hint_vision" : kind == "tools" ? "hint_tools" : "hint_image");
        }

        // ---------- start-up
        void OnLoaded()
        {
            lblHw.Text = "...";
            UpdateAddress(); BuildCards(); UpdateEngineUi(); UpdateServerUi();
            Thread t = new Thread(delegate()
            {
                Hardware h = Hardware.Detect();
                SafeInvoke(delegate
                {
                    hw = h; lblHw.Text = hw.Describe();
                    if (cfg.LlmId.Length == 0) { ModelInfo r = hw.Recommend(models, "llm"); if (r != null) cfg.LlmId = r.Id; cfg.Save(); }
                    BuildCards(); UpdateEngineUi();
                    if (autoSetup && ExeFor("llama") == null) InstallFamily("llama", null);
                    if (cfg.AutoRun && ExeFor("llama") != null) ToggleServer();
                });
            });
            t.IsBackground = true; t.Start();
            if (startMinimized) { BeginInvoke(new Action(delegate { Hide(); })); }
            if (Environment.GetCommandLineArgs().Any(delegate(string x) { return x == "--scroll-test"; }))
            {
                System.Windows.Forms.Timer tm = new System.Windows.Forms.Timer { Interval = 3000 };
                tm.Tick += delegate
                {
                    tm.Stop();
                    string log = Path.Combine(Paths.Root, "scrolltest.log");
                    Action<string> w = delegate(string s) { File.AppendAllText(log, s + Environment.NewLine); };
                    foreach (string k in new[] { "llm", "vision", "image" })
                    {
                        SetKind(k);
                        for (int i = 0; i < 4; i++)
                        {
                            listPanel.AutoScrollPosition = new Point(0, 300 * (i + 1));
                            BuildCards();
                        }
                        int minTop = cards.Values.Count > 0 ? cards.Values.Min(delegate(ModelCard c) { return c.Top; }) : 0;
                        w(k + ": cards=" + cards.Count + " scrollY=" + (-listPanel.AutoScrollPosition.Y) + " vMin=" + listPanel.VerticalScroll.Minimum + " vMax=" + listPanel.VerticalScroll.Maximum +
                          " vLarge=" + listPanel.VerticalScroll.LargeChange + " minChildTop(abs)=" + (minTop + listPanel.AutoScrollPosition.Y));
                    }
                    exiting = true; Close();
                };
                tm.Start();
            }
            if (Environment.GetCommandLineArgs().Any(delegate(string x) { return x == "--open-settings"; }))
                BeginInvoke(new Action(delegate { new SettingsForm(cfg, this).ShowDialog(this); }));
        }

        void BuildCards()
        {
            btnTabLlm.Selected = kind == "llm"; btnTabLlm.Primary = false; btnTabLlm.Invalidate();
            btnTabVision.Selected = kind == "vision"; btnTabVision.Primary = false; btnTabVision.Invalidate();
            btnTabImage.Selected = kind == "image"; btnTabImage.Primary = false; btnTabImage.Invalidate();
            btnTabTools.Selected = kind == "tools"; btnTabTools.Primary = false; btnTabTools.Invalidate();
            loadingUi = true;
            chkOn.Text = Loc.T(kind == "llm" ? "on_llm" : kind == "vision" ? "on_vision" : kind == "tools" ? "on_tools" : "on_image");
            chkOn.Checked = IsOn(kind);
            loadingUi = false;
            // Child locations are relative to the scrolled area: reset the scroll position first, otherwise the cards end up at
            // negative coordinates and the list can be scrolled "upwards" without end. The old position is restored afterwards.
            int keepScroll = -listPanel.AutoScrollPosition.Y;
            listPanel.AutoScrollPosition = new Point(0, 0);
            listPanel.SuspendLayout();
            foreach (ModelCard c in cards.Values) { listPanel.Controls.Remove(c); if (!c.Busy) c.Dispose(); }
            Dictionary<string, ModelCard> keep = new Dictionary<string, ModelCard>();
            foreach (KeyValuePair<string, ModelCard> kv in cards) if (kv.Value.Busy) keep[kv.Key] = kv.Value;
            cards.Clear();
            foreach (KeyValuePair<string, ModelCard> kv in keep) cards[kv.Key] = kv.Value;
            ModelInfo rec = hw.Recommend(models, kind);
            IEnumerable<ModelInfo> all = models.Where(delegate(ModelInfo x) { return x.Kind == kind; })
                .OrderByDescending(delegate(ModelInfo x) { return rec != null && rec.Id == x.Id ? 1 : 0; });
            int y = 0, hidden = 0;
            foreach (ModelInfo m in all)
            {
                int fit = hw.Fit(m);
                bool installed = IsInstalled(m);
                bool sel = SelectedId(kind) == m.Id;
                // keep the list calm: models that do not fit are hidden until the user asks for them
                if (!showAll && fit == 0 && !installed && !sel) { hidden++; continue; }
                ModelCard c;
                if (!cards.TryGetValue(m.Id, out c))
                {
                    c = new ModelCard(m);
                    c.OnMain = OnCardMain; c.OnDelete = OnCardDelete;
                    cards[m.Id] = c;
                }
                c.Fit = fit; c.Recommended = rec != null && rec.Id == m.Id;
                c.Installed = installed;
                c.Active = installed && sel;
                c.Location = new Point(0, y); c.Width = listPanel.ClientSize.Width - 4;
                listPanel.Controls.Add(c);
                c.Refresh_();
                y += c.Height + 10;
            }
            listPanel.AutoScrollMinSize = new Size(0, Math.Max(0, y));
            listPanel.ResumeLayout();
            if (keepScroll > 0) listPanel.AutoScrollPosition = new Point(0, Math.Min(keepScroll, Math.Max(0, y - listPanel.ClientSize.Height)));
            int total = models.Count(delegate(ModelInfo x) { return x.Kind == kind; });
            btnAll.Visible = hidden > 0 || showAll;
            btnAll.Text = showAll ? Loc.T("only_fit") : Loc.F("show_all", hidden);
            emptyNote.Visible = false;
            LayoutAll();
        }

        // ---------- model download / select / delete
        void OnCardMain(ModelCard c)
        {
            ModelInfo m = c.Model;
            if (c.Busy) { cancelFlags[m.Id] = true; return; }
            if (!c.Installed)
            {
                if (c.Fit == 0 && MessageBox.Show(Loc.F("big_confirm", m.Name, m.NeedGb), "Yume LLM Server", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
                StartDownload(c);
                return;
            }
            SetSelected(m.Kind, m.Id);
            BuildCards();
        }

        void OnCardDelete(ModelCard c)
        {
            if (runner.Running) { MessageBox.Show(Loc.T("stop_first"), "Yume LLM Server"); return; }
            try
            {
                File.Delete(Path.Combine(Paths.Models, c.Model.File));
                if (c.Model.Mmproj != null) File.Delete(Path.Combine(Paths.Models, c.Model.Mmproj));
            }
            catch { }
            if (SelectedId(c.Model.Kind) == c.Model.Id) SetSelected(c.Model.Kind, "");
            BuildCards();
        }

        void StartDownload(ModelCard c)
        {
            ModelInfo m = c.Model;
            c.Busy = true; c.Progress = 0; c.Status = ""; cancelFlags[m.Id] = false; c.Refresh_();
            Thread t = new Thread(delegate()
            {
                try
                {
                    List<string> files = new List<string>();
                    files.Add(m.File);
                    if (m.Mmproj != null) files.Add(m.Mmproj);
                    for (int i = 0; i < files.Count; i++)
                    {
                        string f = files[i]; int idx = i; int cnt = files.Count;
                        string dest = Path.Combine(Paths.Models, f);
                        if (File.Exists(dest)) continue;
                        Net.Download("https://huggingface.co/" + m.Repo + "/resolve/main/" + f, dest, delegate(long got, long total)
                        {
                            double frac = total > 0 ? (double)got / total : 0;
                            SafeInvoke(delegate
                            {
                                c.Progress = (idx + frac) / cnt;
                                c.Status = string.Format("{0}  {1:0} / {2:0} MB  ({3:0} %)", f, got / 1048576.0, total > 0 ? total / 1048576.0 : 0, c.Progress * 100);
                                c.Refresh_();
                            });
                        }, delegate { return cancelFlags.ContainsKey(m.Id) && cancelFlags[m.Id]; });
                    }
                    SafeInvoke(delegate
                    {
                        c.Busy = false; c.Installed = IsInstalled(m);
                        if (SelectedId(m.Kind).Length == 0) SetSelected(m.Kind, m.Id);
                        BuildCards();
                    });
                }
                catch (OperationCanceledException)
                {
                    SafeInvoke(delegate { c.Busy = false; c.Status = ""; c.Refresh_(); });
                }
                catch (Exception ex)
                {
                    SafeInvoke(delegate { c.Busy = false; c.Status = ""; c.Refresh_(); MessageBox.Show(Loc.F("dl_fail", ex.Message), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Warning); });
                }
            });
            t.IsBackground = true; t.Start();
        }

        // ---------- engines
        void UpdateEngineUi()
        {
            string family = FamilyOf(kind);
            string type = EngineTypeFor(family);
            bool ok = ExeFor(family) != null;
            string ver = family == "sd" ? ImageEngine.InstalledVersion(type) : Engine.InstalledVersion(type);
            string label = (family == "sd" ? Loc.T("eng_img") : Loc.T("eng_llm"));
            lblEngineStatus.Text = label + ": " + type.ToUpperInvariant() + " - " + (ok ? Loc.T("engine_ok") + (ver.Length > 0 ? " (" + ver + ")" : "") : Loc.T("engine_missing"));
            lblEngineStatus.ForeColor = ok ? Theme.Ok : Theme.Warn;
            btnEngine.Visible = !ok && !installing;
            btnEngine.Text = Loc.T("engine_install");
            btnEngine.Primary = true;
        }

        public void InstallFamily(string family, Action done)
        {
            if (installing) return;
            installing = true;
            string type = EngineTypeFor(family);
            btnEngine.Visible = false; btnStart.Enabled = false; engineBar.Visible = true; engineBar.Value = 0;
            Thread t = new Thread(delegate()
            {
                try
                {
                    Engine.EnsureVcRuntime(delegate(string s) { SafeInvoke(delegate { lblEngineStatus.Text = s; }); });
                    Action<double, string> prog = delegate(double f, string text)
                    {
                        SafeInvoke(delegate { engineBar.Value = f; lblEngineStatus.ForeColor = Theme.Lav; lblEngineStatus.Text = Loc.F("installing", text); });
                    };
                    if (family == "sd") ImageEngine.Install(type, hw, prog, null); else Engine.Install(type, hw, prog, null);
                    SafeInvoke(delegate
                    {
                        installing = false; engineBar.Visible = false; btnStart.Enabled = true;
                        UpdateEngineUi(); lblEngineStatus.Text = Loc.F("engine_done", type.ToUpperInvariant());
                        if (done != null) done();
                    });
                }
                catch (Exception ex)
                {
                    SafeInvoke(delegate
                    {
                        installing = false; engineBar.Visible = false; btnStart.Enabled = true; UpdateEngineUi();
                        MessageBox.Show(Loc.F("engine_fail", ex.Message), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    });
                }
            });
            t.IsBackground = true; t.Start();
        }

        // ---------- server
        void ToggleServer()
        {
            if (InvokeRequired) { BeginInvoke(new Action(ToggleServer)); return; }
            if (runner.Running) { runner.Stop(); UpdateServerUi(); return; }
            ModelInfo llm = cfg.LlmOn ? Selected("llm") : null;
            ModelInfo vis = cfg.VisionOn ? Selected("vision") : null;
            ModelInfo img = cfg.ImageOn ? Selected("image") : null;
            ModelInfo tl = cfg.ToolsOn ? Selected("tools") : null;
            if (tl != null && !IsInstalled(tl)) tl = null;
            if (llm != null && !IsInstalled(llm)) llm = null;
            if (vis != null && !IsInstalled(vis)) vis = null;
            if (img != null && !IsInstalled(img)) img = null;
            if (llm == null && vis == null && img == null && tl == null)
            {
                // nothing is switched on, but the model of the open tab is ready: that is clearly what is meant
                ModelInfo here = Selected(kind);
                if (here != null && IsInstalled(here))
                {
                    SetOn(kind, true); BuildCards();
                    if (kind == "llm") llm = here; else if (kind == "vision") vis = here; else if (kind == "tools") tl = here; else img = here;
                }
            }
            if (llm == null && vis == null && img == null && tl == null) { MessageBox.Show(Loc.T("need_model"), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
            bool needLlama = llm != null || vis != null || tl != null;
            if (needLlama && ExeFor("llama") == null)
            {
                if (MessageBox.Show(Loc.T("need_engine"), "Yume LLM Server", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                    InstallFamily("llama", delegate { ToggleServer(); });
                return;
            }
            if (img != null && ExeFor("sd") == null)
            {
                if (MessageBox.Show(Loc.T("need_engine_img"), "Yume LLM Server", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                    InstallFamily("sd", delegate { ToggleServer(); });
                return;
            }
            foreach (ModelInfo big in new[] { llm, vis, tl })
                if (big != null && hw.Discrete && hw.Fit(big) == 0 && MessageBox.Show(Loc.T("big_start"), "Yume LLM Server", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
            string lt = EngineTypeFor("llama"), st = EngineTypeFor("sd");
            bool offload = img != null && hw.Discrete && img.NeedGb > hw.UsableGb;
            runner.Start(needLlama ? ExeFor("llama") : null, lt != "cpu", cfg, llm, vis, img, img != null ? ExeFor("sd") : null, offload, tl);
            UpdateServerUi();
        }

        void UpdateServerUi()
        {
            bool run = runner.Running;
            bool anyReady = (runner.Llm != null && runner.LlmReady) || (runner.Vision != null && runner.VisionReady) || (runner.Image != null && runner.ImageReady) || (runner.Tools != null && runner.ToolsReady);
            bool allReady = (runner.Llm == null || runner.LlmReady || runner.Llm.HasExited) && (runner.Vision == null || runner.VisionReady || runner.Vision.HasExited)
                && (runner.Image == null || runner.ImageReady || runner.Image.HasExited) && (runner.Tools == null || runner.ToolsReady || runner.Tools.HasExited);
            btnStart.Text = run ? Loc.T("stop") : Loc.T("start");
            btnStart.Primary = !run; btnStart.Invalidate();
            bool ready = run && anyReady && allReady;
            if (!run && runner.Llm == null && runner.Vision == null && runner.Image == null && runner.Tools == null) { lblStatus.Text = Loc.T("stopped"); lblStatus.ForeColor = Theme.Muted; }
            else if (ready) { lblStatus.Text = "● " + Loc.T("running"); lblStatus.ForeColor = Theme.Ok; MaybeAskFirewall(); }
            else if (run) { lblStatus.Text = "● " + Loc.T("starting"); lblStatus.ForeColor = Theme.Warn; }
            tray.Text = "Yume LLM Server - " + (ready ? Loc.T("running") : run ? Loc.T("starting") : Loc.T("stopped"));
            if (!run && (runner.Llm != null || runner.Vision != null || runner.Image != null || runner.Tools != null))
            {
                lblStatus.Text = "● " + Loc.T("crashed"); lblStatus.ForeColor = Theme.Bad;
                runner.Llm = runner.Vision = runner.Image = runner.Tools = null;
                new LogForm().Show(this);
            }
        }

        static bool FirewallRuleExists()
        {
            try { return Hardware.Run("netsh", "advfirewall firewall show rule name=\"Yume LLM Server\"", 8000).IndexOf("Yume LLM Server", StringComparison.OrdinalIgnoreCase) >= 0; }
            catch { return true; }
        }

        bool fwChecked;
        void MaybeAskFirewall()
        {
            if (fwChecked || cfg.FwAsked || !cfg.Lan) return;
            fwChecked = true;
            Thread t = new Thread(delegate()
            {
                if (FirewallRuleExists()) return;
                SafeInvoke(delegate
                {
                    cfg.FwAsked = true; cfg.Save();
                    if (MessageBox.Show(Loc.T("fw_ask"), "Yume LLM Server", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes) OpenFirewall();
                });
            });
            t.IsBackground = true; t.Start();
        }

        public void OpenFirewall()
        {
            try
            {
                string ports = cfg.Port + "-" + (cfg.Port + 2);
                ProcessStartInfo psi = new ProcessStartInfo("netsh", "advfirewall firewall add rule name=\"Yume LLM Server\" dir=in action=allow protocol=TCP localport=" + ports + " profile=private,domain");
                psi.Verb = "runas"; psi.UseShellExecute = true; psi.WindowStyle = ProcessWindowStyle.Hidden;
                using (Process p = Process.Start(psi)) { p.WaitForExit(15000); }
                MessageBox.Show(Loc.T("fw_done"), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch { MessageBox.Show(Loc.T("fw_fail"), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        }

        public static void SetAutostart(bool on)
        {
            try
            {
                using (RegistryKey k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", true))
                {
                    if (on) k.SetValue("YumeLLMServer", "\"" + Application.ExecutablePath + "\" --minimized");
                    else k.DeleteValue("YumeLLMServer", false);
                }
            }
            catch { }
        }
    }
}
