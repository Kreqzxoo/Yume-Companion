// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in this folder.
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
            RoundButton bUpdLlm = new RoundButton { Text = Loc.T("engine_update"), Primary = false, Width = 110, Height = 28, Location = new Point(440, y - 1), Font = Theme.F(8.5f, FontStyle.Bold) };
            Controls.Add(cbEngLlm); Controls.Add(bUpdLlm); y += 38;
            Controls.Add(L(Loc.T("eng_img"), 20, y + 4, false));
            cbEngImg = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200, Location = new Point(230, y), FlatStyle = FlatStyle.Flat, BackColor = Theme.Panel2, ForeColor = Theme.Text };
            cbEngImg.Items.AddRange(new object[] { Loc.T("engine_auto") + " (Vulkan)", "CUDA (NVIDIA)", "Vulkan", "CPU" });
            RoundButton bUpdImg = new RoundButton { Text = Loc.T("engine_update"), Primary = false, Width = 110, Height = 28, Location = new Point(440, y - 1), Font = Theme.F(8.5f, FontStyle.Bold) };
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
        bool showAll, exiting, startMinimized, autoSetup, installing;
        readonly Dictionary<string, ModelCard> cards = new Dictionary<string, ModelCard>();
        readonly Dictionary<string, bool> cancelFlags = new Dictionary<string, bool>();
        EventWaitHandle exitEvent;

        Label lblTitle, lblSub, lblStatus, lblHw, lblEngineStatus, lblAddr, lblHint;
        RoundButton btnStart, btnTabLlm, btnTabVision, btnTabImage, btnEngine, btnCopy, btnSettings, btnAll;
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
            btnSettings = new RoundButton { Text = "⚙  " + Loc.T("settings"), Primary = false, Width = 150, Height = 34 };
            btnTabLlm.Click += delegate { SetKind("llm"); };
            btnTabVision.Click += delegate { SetKind("vision"); };
            btnTabImage.Click += delegate { SetKind("image"); };
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
            Controls.Add(btnTabLlm); Controls.Add(btnTabVision); Controls.Add(btnTabImage); Controls.Add(btnSettings); Controls.Add(strip); Controls.Add(header);
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
            btnTabLlm.Location = new Point(m, ty); btnTabVision.Location = new Point(m + 156, ty); btnTabImage.Location = new Point(m + 312, ty);
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
        int PortOf(string k) { return k == "llm" ? cfg.Port : k == "vision" ? cfg.Port + 1 : cfg.Port + 2; }
        string UrlFor(string k) { return "http://" + (cfg.Lan ? LocalIp() : "127.0.0.1") + ":" + PortOf(k); }
        string CurrentUrl() { return UrlFor(kind); }

        bool IsOn(string k) { return k == "llm" ? cfg.LlmOn : k == "vision" ? cfg.VisionOn : cfg.ImageOn; }
        void SetOn(string k, bool v) { if (k == "llm") cfg.LlmOn = v; else if (k == "vision") cfg.VisionOn = v; else cfg.ImageOn = v; cfg.Save(); }
        string SelectedId(string k) { return k == "llm" ? cfg.LlmId : k == "vision" ? cfg.VisionId : cfg.ImageId; }
        void SetSelected(string k, string id) { if (k == "llm") cfg.LlmId = id; else if (k == "vision") cfg.VisionId = id; else cfg.ImageId = id; cfg.Save(); }

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

        void SetKind(string k) { kind = k; showAll = false; BuildCards(); UpdateEngineUi(); UpdateAddress(); }

        void UpdateAddress()
        {
            lblAddr.Text = CurrentUrl();
            btnCopy.Text = Loc.T("copy");
            lblHint.Text = Loc.T(kind == "llm" ? "hint_llm" : kind == "vision" ? "hint_vision" : "hint_image");
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
        }

        void BuildCards()
        {
            btnTabLlm.Selected = kind == "llm"; btnTabLlm.Primary = false; btnTabLlm.Invalidate();
            btnTabVision.Selected = kind == "vision"; btnTabVision.Primary = false; btnTabVision.Invalidate();
            btnTabImage.Selected = kind == "image"; btnTabImage.Primary = false; btnTabImage.Invalidate();
            loadingUi = true;
            chkOn.Text = Loc.T(kind == "llm" ? "on_llm" : kind == "vision" ? "on_vision" : "on_image");
            chkOn.Checked = IsOn(kind);
            loadingUi = false;
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
            listPanel.ResumeLayout();
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
            if (!c.Installed) { StartDownload(c); return; }
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
            if (llm != null && !IsInstalled(llm)) llm = null;
            if (vis != null && !IsInstalled(vis)) vis = null;
            if (img != null && !IsInstalled(img)) img = null;
            if (llm == null && vis == null && img == null) { MessageBox.Show(Loc.T("need_model"), "Yume LLM Server", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
            bool needLlama = llm != null || vis != null;
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
            string lt = EngineTypeFor("llama"), st = EngineTypeFor("sd");
            bool offload = img != null && hw.Discrete && img.NeedGb > hw.UsableGb;
            runner.Start(needLlama ? ExeFor("llama") : null, lt != "cpu", cfg, llm, vis, img, img != null ? ExeFor("sd") : null, offload);
            UpdateServerUi();
        }

        void UpdateServerUi()
        {
            bool run = runner.Running;
            bool anyReady = (runner.Llm != null && runner.LlmReady) || (runner.Vision != null && runner.VisionReady) || (runner.Image != null && runner.ImageReady);
            bool allReady = (runner.Llm == null || runner.LlmReady || runner.Llm.HasExited) && (runner.Vision == null || runner.VisionReady || runner.Vision.HasExited)
                && (runner.Image == null || runner.ImageReady || runner.Image.HasExited);
            btnStart.Text = run ? Loc.T("stop") : Loc.T("start");
            btnStart.Primary = !run; btnStart.Invalidate();
            bool ready = run && anyReady && allReady;
            if (!run && runner.Llm == null && runner.Vision == null && runner.Image == null) { lblStatus.Text = Loc.T("stopped"); lblStatus.ForeColor = Theme.Muted; }
            else if (ready) { lblStatus.Text = "● " + Loc.T("running"); lblStatus.ForeColor = Theme.Ok; MaybeAskFirewall(); }
            else if (run) { lblStatus.Text = "● " + Loc.T("starting"); lblStatus.ForeColor = Theme.Warn; }
            tray.Text = "Yume LLM Server - " + (ready ? Loc.T("running") : run ? Loc.T("starting") : Loc.T("stopped"));
            if (!run && (runner.Llm != null || runner.Vision != null || runner.Image != null))
            {
                lblStatus.Text = "● " + Loc.T("crashed"); lblStatus.ForeColor = Theme.Bad;
                runner.Llm = runner.Vision = runner.Image = null;
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
