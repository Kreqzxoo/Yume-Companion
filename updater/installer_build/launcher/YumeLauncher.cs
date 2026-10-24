// Yume Companion launcher: starts the program without a console window and shows an animated anime-style splash
// screen (falling sakura petals, twinkling stars, a hopping mascot on the progress bar) with a 0-100 % progress bar.
// The program (main.py) reports its progress through the file named in the environment variable YUME_BOOT_FILE
// ("percent|stage"); the splash fades out when 100 % is reached.
//
// Build: csc /target:winexe ... (see installer_build\build.bat)

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

static class Program
{
    [DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();

    [STAThread]
    static void Main()
    {
        try { SetProcessDPIAware(); } catch { }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        string appDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        string id;
        using (var md5 = MD5.Create())
            id = BitConverter.ToString(md5.ComputeHash(Encoding.UTF8.GetBytes(appDir.ToLowerInvariant()))).Replace("-", "");
        bool created;
        using (var mutex = new Mutex(true, "YumeCompanionLauncher_" + id, out created))
        {
            if (!created) return; // already starting
            Application.Run(new SplashForm(appDir));
        }
    }
}

class Petal
{
    public float X, Y, Size, Speed, Sway, Phase, Rot, Spin, Alpha;
}

class Twinkle
{
    public float X, Y, Size, Speed, Phase;
}

class Spark
{
    public float X, Y, Vx, Vy, Life, Size;
}

class SplashForm : Form
{
    readonly string appDir, bootFile, errorLog;
    readonly bool german = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "de";
    string appName = "Yume Companion", version = "";
    Image icon, roundIcon;
    Process proc;
    System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    double shown = 0;
    int target = 0;
    string stage = "";
    DateTime started, lastChange, lastRead = DateTime.MinValue, closingSince = DateTime.MinValue;
    bool failed;

    // animation state
    readonly Random rnd = new Random(11);
    readonly List<Petal> petals = new List<Petal>();
    readonly List<Twinkle> twinkles = new List<Twinkle>();
    readonly List<Spark> sparks = new List<Spark>();
    DateTime lastFrame = DateTime.Now;
    float clock = 0f;

    static readonly Color Accent = Color.FromArgb(255, 168, 214), Muted = Color.FromArgb(214, 200, 226);

    public SplashForm(string dir)
    {
        appDir = dir;
        bootFile = Path.Combine(appDir, "app", "cache", "boot_progress.txt");
        errorLog = Path.Combine(appDir, "logs", "launcher_error.log");
        LoadBranding();

        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        ShowInTaskbar = false;
        TopMost = true;
        DoubleBuffered = true;
        ClientSize = new Size(640, 360);
        Text = appName;
        Opacity = 0;
        Region = new Region(RoundedRect(new Rectangle(0, 0, Width, Height), 22));
        timer.Interval = 33;
        timer.Tick += OnTick;
        Shown += OnShown;

        for (int i = 0; i < 26; i++) petals.Add(NewPetal(true));
        for (int i = 0; i < 24; i++)
            twinkles.Add(new Twinkle
            {
                X = (float)rnd.NextDouble() * 640, Y = (float)rnd.NextDouble() * 210,
                Size = 2f + (float)rnd.NextDouble() * 3.5f, Speed = 1.2f + (float)rnd.NextDouble() * 2.4f,
                Phase = (float)rnd.NextDouble() * 6.28f
            });
    }

    Petal NewPetal(bool anywhere)
    {
        return new Petal
        {
            X = (float)rnd.NextDouble() * 660 - 10,
            Y = anywhere ? (float)rnd.NextDouble() * 360 : -20,
            Size = 5f + (float)rnd.NextDouble() * 7f,
            Speed = 22f + (float)rnd.NextDouble() * 34f,
            Sway = 14f + (float)rnd.NextDouble() * 26f,
            Phase = (float)rnd.NextDouble() * 6.28f,
            Rot = (float)rnd.NextDouble() * 360f,
            Spin = -90f + (float)rnd.NextDouble() * 180f,
            Alpha = 0.45f + (float)rnd.NextDouble() * 0.45f
        };
    }

    void LoadBranding()
    {
        try
        {
            string vf = Path.Combine(appDir, "VERSION.txt");
            if (File.Exists(vf)) version = File.ReadAllText(vf).Trim();
        }
        catch { }
        string iconPath = null;
        try
        {
            string bf = Path.Combine(appDir, "app", "configuration", "branding.json");
            if (File.Exists(bf))
            {
                var data = new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string, object>>(File.ReadAllText(bf));
                object v;
                if (data.TryGetValue("app_name", out v) && v is string && ((string)v).Trim().Length > 0) appName = ((string)v).Trim();
                foreach (string key in new[] { "app_icon_path", "logo_path" })
                    if (iconPath == null && data.TryGetValue(key, out v) && v is string && ((string)v).Length > 0)
                    {
                        string p = Path.Combine(appDir, ((string)v).Replace('/', '\\'));
                        if (File.Exists(p)) iconPath = p;
                    }
            }
        }
        catch { }
        if (iconPath == null) iconPath = Path.Combine(appDir, "app", "gui", "icons", "logotype.png");
        try { if (File.Exists(iconPath)) icon = SquareImage(Image.FromFile(iconPath)); } catch { }
        try { if (icon != null) roundIcon = MakeRound(icon, 240); } catch { }
    }

    // Round, anti-aliased badge: the app icon is a rounded square with transparent margins and a glow, so the
    // circle is cut slightly inside the full image (corners trimmed, art and lettering stay visible).
    static RectangleF AlphaBounds(Image src)
    {
        const int n = 160;
        using (var small = new Bitmap(n, n, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
        {
            using (var g = Graphics.FromImage(small))
            {
                g.Clear(Color.Transparent);
                g.InterpolationMode = InterpolationMode.HighQualityBilinear;
                g.DrawImage(src, new Rectangle(0, 0, n, n));
            }
            int minX = n, minY = n, maxX = -1, maxY = -1;
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                    if (small.GetPixel(x, y).A > 170)
                    {
                        if (x < minX) minX = x; if (x > maxX) maxX = x;
                        if (y < minY) minY = y; if (y > maxY) maxY = y;
                    }
            if (maxX < 0) return new RectangleF(0, 0, src.Width, src.Height);
            float kx = src.Width / (float)n, ky = src.Height / (float)n;
            return new RectangleF(minX * kx, minY * ky, (maxX - minX + 1) * kx, (maxY - minY + 1) * ky);
        }
    }

    static Image MakeRound(Image src, int size)
    {
        var bmp = new Bitmap(size, size, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            var all = new Rectangle(0, 0, size, size);
            using (var back = new LinearGradientBrush(all, Color.FromArgb(46, 28, 62), Color.FromArgb(24, 14, 38), 90f))
                g.FillEllipse(back, all);
            // measure the visible art (transparent margins/glow are ignored) and cut the circle inside it
            RectangleF art = AlphaBounds(src);
            float side = Math.Min(art.Width, art.Height) * 0.985f;
            float sx = art.X + (art.Width - side) / 2f;
            float sy = art.Y + (art.Height - side) / 2f + art.Height * 0.025f;  // slightly down: keeps the lettering
            using (var tb = new TextureBrush(src, WrapMode.Clamp))
            {
                tb.ResetTransform();
                tb.TranslateTransform(-sx, -sy);
                tb.ScaleTransform(size / side, size / side, MatrixOrder.Append);
                g.FillEllipse(tb, all);
            }
        }
        return bmp;
    }

    static Image SquareImage(Image src)
    {
        int side = Math.Min(src.Width, src.Height);
        var bmp = new Bitmap(side, side);
        using (var g = Graphics.FromImage(bmp))
            g.DrawImage(src, new Rectangle(0, 0, side, side), new Rectangle((src.Width - side) / 2, (src.Height - side) / 2, side, side), GraphicsUnit.Pixel);
        return bmp;
    }

    static GraphicsPath RoundedRect(Rectangle r, int radius)
    {
        var path = new GraphicsPath();
        int d = radius * 2;
        path.AddArc(r.X, r.Y, d, d, 180, 90);
        path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    void OnShown(object sender, EventArgs e)
    {
        started = lastChange = DateTime.Now;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(bootFile));
            Directory.CreateDirectory(Path.GetDirectoryName(errorLog));
            if (File.Exists(bootFile)) File.Delete(bootFile);
            if (File.Exists(errorLog)) File.Delete(errorLog);
        }
        catch { }

        string cmd = "call \"" + Path.Combine(appDir, "app", "data", "Scripts", "activate.bat") + "\" app/data/envs/sow >nul 2>&1"
                   + " && set \"PATH=" + Path.Combine(appDir, "app", "ffmpeg", "bin") + ";!PATH!\""
                   + " && python main.py 2>>\"" + errorLog + "\"";
        var psi = new ProcessStartInfo("cmd.exe", "/v:on /c \"" + cmd + "\"")
        {
            WorkingDirectory = appDir,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        psi.EnvironmentVariables["YUME_BOOT_FILE"] = bootFile;
        try { proc = Process.Start(psi); }
        catch (Exception ex) { Fail(ex.Message); return; }
        timer.Start();
    }

    void ReadProgress()
    {
        if ((DateTime.Now - lastRead).TotalMilliseconds < 150) return;
        lastRead = DateTime.Now;
        try
        {
            using (var fs = new FileStream(bootFile, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            using (var sr = new StreamReader(fs))
            {
                string[] parts = sr.ReadToEnd().Trim().Split('|');
                int p;
                if (parts.Length > 0 && int.TryParse(parts[0], out p))
                {
                    p = Math.Max(0, Math.Min(100, p));
                    if (p > target) { target = p; lastChange = DateTime.Now; }
                    if (parts.Length > 1) stage = parts[1];
                }
            }
        }
        catch { }
    }

    string StageText()
    {
        switch (stage)
        {
            case "start": return german ? "Yume wacht auf" : "Yume is waking up";
            case "libraries": return german ? "Sammle Sternenstaub" : "Gathering stardust";
            case "interface": return german ? "Richte die Schleife zurecht" : "Fixing her ribbon";
            case "window": return german ? "Gleich ist sie da" : "Almost there";
            case "ready": return german ? "Bereit!" : "Ready!";
            default: return german ? "Yume wacht auf" : "Yume is waking up";
        }
    }

    void OnTick(object sender, EventArgs e)
    {
        try { Tick(); }
        catch (Exception ex) { timer.Stop(); Log("tick: " + ex); Fail(ex.Message); }
    }

    void Log(string text)
    {
        try { File.AppendAllText(Path.Combine(appDir, "logs", "launcher.log"), DateTime.Now.ToString("s") + " " + text + Environment.NewLine); } catch { }
    }

    float MascotX()
    {
        float trackX = 44, trackW = Width - 88;
        float w = (float)(trackW * Math.Max(0, Math.Min(100, shown)) / 100.0);
        return trackX + Math.Max(10f, Math.Min(trackW - 6f, w));
    }

    void Animate()
    {
        var now = DateTime.Now;
        float dt = (float)Math.Min(0.1, (now - lastFrame).TotalSeconds);
        lastFrame = now;
        clock += dt;
        foreach (var p in petals)
        {
            p.Y += p.Speed * dt;
            p.X += (float)Math.Sin(clock * 0.9f + p.Phase) * p.Sway * dt + 6f * dt;
            p.Rot += p.Spin * dt;
        }
        for (int i = 0; i < petals.Count; i++)
            if (petals[i].Y > Height + 20 || petals[i].X > Width + 30) petals[i] = NewPetal(false);

        // sparkle trail behind the mascot
        if (shown < 99.5 && rnd.NextDouble() < 0.55)
        {
            float hop = (float)Math.Abs(Math.Sin(clock * 9.0)) * 8f;
            sparks.Add(new Spark
            {
                X = MascotX() - 6 + (float)rnd.NextDouble() * 6f, Y = 262 - hop + (float)rnd.NextDouble() * 10f,
                Vx = -18f - (float)rnd.NextDouble() * 22f, Vy = -10f - (float)rnd.NextDouble() * 20f,
                Life = 1f, Size = 2.5f + (float)rnd.NextDouble() * 3.5f
            });
        }
        for (int i = sparks.Count - 1; i >= 0; i--)
        {
            var s = sparks[i];
            s.X += s.Vx * dt; s.Y += s.Vy * dt; s.Life -= dt * 1.4f;
            if (s.Life <= 0) sparks.RemoveAt(i);
        }
    }

    void Tick()
    {
        ReadProgress();
        Animate();

        if (closingSince != DateTime.MinValue)
        {
            double t = (DateTime.Now - closingSince).TotalSeconds / 0.35;
            if (t >= 1) { timer.Stop(); Close(); return; }
            Opacity = Math.Max(0, 1 - t);
            Invalidate();
            return;
        }
        if (Opacity < 1) Opacity = Math.Min(1, Opacity + 0.12);

        if (proc != null && proc.HasExited && target < 100)
        {
            timer.Stop();
            string tail = "";
            try
            {
                if (File.Exists(errorLog))
                {
                    string[] lines = File.ReadAllLines(errorLog);
                    int from = Math.Max(0, lines.Length - 12);
                    tail = string.Join("\n", lines, from, lines.Length - from);
                }
            }
            catch { }
            Fail(tail);
            return;
        }

        // glide towards the reported value; a slow creep keeps the bar alive between milestones
        double ceiling = target >= 100 ? 100 : Math.Min(95, target + 12);
        double goal = target >= 100 ? 100 : Math.Min(ceiling, target + (DateTime.Now - lastChange).TotalSeconds * 0.8);
        if (shown < goal) shown = Math.Min(goal, shown + Math.Max(0.15, (goal - shown) * 0.08));
        Invalidate();

        if (target >= 100 && shown >= 99.5)
        {
            closingSince = DateTime.Now.AddMilliseconds(450); // short happy moment, then fade out
            return;
        }
        if ((DateTime.Now - started).TotalSeconds > 240) { timer.Stop(); Close(); }
    }

    void Fail(string details)
    {
        failed = true;
        Log("start failed: " + details);
        TopMost = false;
        Opacity = 1;
        string head = german
            ? appName + " konnte nicht gestartet werden."
            : appName + " could not be started.";
        string hint = german
            ? "Fehlende Komponenten? Starte im Startmenü \"Komponenten installieren oder reparieren\".\nDetails: Ordner \"logs\" im Programmverzeichnis."
            : "Missing components? Run \"Install or repair components\" from the Start menu.\nDetails: the \"logs\" folder in the program directory.";
        MessageBox.Show(head + "\n\n" + (string.IsNullOrWhiteSpace(details) ? "" : details + "\n\n") + hint,
                        appName, MessageBoxButtons.OK, MessageBoxIcon.Error);
        Close();
    }

    // ------------------------------------------------------------------ drawing helpers
    static GraphicsPath PetalPath(float s)
    {
        var path = new GraphicsPath();
        path.AddBezier(0, -s, s * 0.95f, -s * 0.7f, s * 0.8f, s * 0.7f, 0, s);
        path.AddBezier(0, s, -s * 0.8f, s * 0.7f, -s * 0.95f, -s * 0.7f, 0, -s);
        // little notch at the tip like a real sakura petal
        return path;
    }

    static GraphicsPath StarPath(float cx, float cy, float r)
    {
        var path = new GraphicsPath();
        float ri = r * 0.28f;
        var pts = new PointF[8];
        for (int i = 0; i < 8; i++)
        {
            float rad = (i % 2 == 0) ? r : ri;
            double a = -Math.PI / 2 + i * Math.PI / 4;
            pts[i] = new PointF(cx + (float)(Math.Cos(a) * rad), cy + (float)(Math.Sin(a) * rad));
        }
        path.AddPolygon(pts);
        return path;
    }

    static GraphicsPath HeartPath(float cx, float cy, float s)
    {
        var path = new GraphicsPath();
        path.AddBezier(cx, cy + s * 0.9f, cx - s * 1.5f, cy - s * 0.1f, cx - s * 0.7f, cy - s * 1.2f, cx, cy - s * 0.4f);
        path.AddBezier(cx, cy - s * 0.4f, cx + s * 0.7f, cy - s * 1.2f, cx + s * 1.5f, cy - s * 0.1f, cx, cy + s * 0.9f);
        return path;
    }

    void DrawMascot(Graphics g, float cx, float cy, bool happy)
    {
        float hop = happy ? (float)Math.Abs(Math.Sin(clock * 12.0)) * 12f : (float)Math.Abs(Math.Sin(clock * 9.0)) * 8f;
        float squash = 1f + (float)Math.Sin(clock * 9.0) * 0.04f;
        float y = cy - hop;
        var state = g.Save();
        g.TranslateTransform(cx, y);
        g.ScaleTransform(1f / squash, squash);

        // shadow on the bar
        using (var sh = new SolidBrush(Color.FromArgb((int)(60 - hop * 3), 0, 0, 0)))
            g.FillEllipse(sh, -9 + hop * 0.2f, 16 + hop, 18 - hop * 0.4f, 4);

        // ears
        using (var ear = new SolidBrush(Color.FromArgb(255, 246, 250)))
        using (var earIn = new SolidBrush(Color.FromArgb(255, 160, 205)))
        using (var edge = new Pen(Color.FromArgb(255, 150, 200), 1.4f))
        {
            var l = new[] { new PointF(-12, -6), new PointF(-9, -19), new PointF(-2, -11) };
            var r = new[] { new PointF(12, -6), new PointF(9, -19), new PointF(2, -11) };
            g.FillPolygon(ear, l); g.FillPolygon(ear, r);
            g.DrawPolygon(edge, l); g.DrawPolygon(edge, r);
            g.FillPolygon(earIn, new[] { new PointF(-10, -8), new PointF(-9, -15), new PointF(-5, -10) });
            g.FillPolygon(earIn, new[] { new PointF(10, -8), new PointF(9, -15), new PointF(5, -10) });
        }
        // body / head
        var body = new RectangleF(-14, -12, 28, 28);
        using (var br = new LinearGradientBrush(body, Color.FromArgb(255, 252, 254), Color.FromArgb(255, 226, 240), 90f))
            g.FillEllipse(br, body);
        using (var pen = new Pen(Color.FromArgb(255, 150, 200), 1.6f)) g.DrawEllipse(pen, body);

        // ribbon
        using (var rb = new SolidBrush(Color.FromArgb(255, 110, 170)))
        {
            g.FillPolygon(rb, new[] { new PointF(8, -12), new PointF(16, -17), new PointF(15, -8) });
            g.FillPolygon(rb, new[] { new PointF(8, -12), new PointF(2, -19), new PointF(1, -9) });
            g.FillEllipse(rb, 5, -15, 6, 6);
        }
        // face
        double sinceBlink = (clock % 3.2);
        bool blink = sinceBlink > 3.08;
        using (var eye = new SolidBrush(Color.FromArgb(70, 40, 90)))
        using (var eyePen = new Pen(Color.FromArgb(70, 40, 90), 1.8f))
        {
            if (happy)
            {
                g.DrawArc(eyePen, -9, -2, 7, 6, 200, 140);
                g.DrawArc(eyePen, 2, -2, 7, 6, 200, 140);
            }
            else if (blink)
            {
                g.DrawLine(eyePen, -9, 2, -3, 2);
                g.DrawLine(eyePen, 3, 2, 9, 2);
            }
            else
            {
                g.FillEllipse(eye, -9, -3, 6, 8);
                g.FillEllipse(eye, 3, -3, 6, 8);
                using (var hl = new SolidBrush(Color.White)) { g.FillEllipse(hl, -7.5f, -2, 2.4f, 2.4f); g.FillEllipse(hl, 4.5f, -2, 2.4f, 2.4f); }
            }
            using (var mouth = new Pen(Color.FromArgb(200, 90, 140), 1.4f))
                g.DrawArc(mouth, -3.5f, 5, 7, 5, 20, 140);
        }
        using (var cheek = new SolidBrush(Color.FromArgb(120, 255, 130, 180)))
        {
            g.FillEllipse(cheek, -13, 4, 6, 4);
            g.FillEllipse(cheek, 7, 4, 6, 4);
        }
        g.Restore(state);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
        var rect = new Rectangle(0, 0, Width, Height);

        // night sky -> sakura dusk
        using (var br = new LinearGradientBrush(rect, Color.FromArgb(20, 14, 38), Color.FromArgb(78, 36, 82), 90f))
        {
            var blend = new ColorBlend(4);
            blend.Colors = new[] { Color.FromArgb(20, 14, 38), Color.FromArgb(44, 24, 66), Color.FromArgb(96, 44, 98), Color.FromArgb(150, 70, 120) };
            blend.Positions = new[] { 0f, 0.45f, 0.8f, 1f };
            br.InterpolationColors = blend;
            g.FillRectangle(br, rect);
        }

        // big soft moon glow
        float pulse = 1f + (float)Math.Sin(clock * 1.4f) * 0.05f;
        using (var gp = new GraphicsPath())
        {
            float rad = 150f * pulse;
            gp.AddEllipse(Width * 0.5f - rad, 70 - rad * 0.8f, rad * 2, rad * 1.6f);
            using (var pg = new PathGradientBrush(gp))
            {
                pg.CenterColor = Color.FromArgb(70, 255, 170, 220);
                pg.SurroundColors = new[] { Color.FromArgb(0, 255, 170, 220) };
                g.FillPath(pg, gp);
            }
        }

        // twinkling stars
        foreach (var t in twinkles)
        {
            float a = 0.25f + 0.75f * (float)Math.Abs(Math.Sin(clock * t.Speed + t.Phase));
            using (var sp = StarPath(t.X, t.Y, t.Size * (0.7f + 0.5f * a)))
            using (var br = new SolidBrush(Color.FromArgb((int)(210 * a), 255, 235, 248)))
                g.FillPath(br, sp);
        }

        // distant sakura branch silhouettes (decor) at the top corners
        using (var pen = new Pen(Color.FromArgb(70, 40, 20, 50), 5f))
        {
            pen.StartCap = LineCap.Round; pen.EndCap = LineCap.Round;
            g.DrawCurve(pen, new[] { new PointF(-10, 40), new PointF(60, 24), new PointF(120, 40), new PointF(170, 18) });
            g.DrawCurve(pen, new[] { new PointF(Width + 10, 30), new PointF(Width - 70, 14), new PointF(Width - 130, 34) });
        }
        using (var bl = new SolidBrush(Color.FromArgb(110, 255, 170, 214)))
        {
            foreach (var p in new[] { new PointF(60, 25), new PointF(112, 38), new PointF(150, 22), new PointF(Width - 70, 16), new PointF(Width - 118, 31) })
                for (int k = 0; k < 5; k++)
                {
                    double a = k * Math.PI * 2 / 5 + 0.3;
                    g.FillEllipse(bl, p.X + (float)Math.Cos(a) * 5 - 4, p.Y + (float)Math.Sin(a) * 5 - 4, 8, 8);
                }
        }

        // logo with breathing ring
        float bob = (float)Math.Sin(clock * 1.7f) * 3f;
        var iconRect = new RectangleF(46, 66 + bob, 134, 134);
        using (var ring = new Pen(Color.FromArgb((int)(90 + 50 * Math.Sin(clock * 2.0f)), 255, 160, 210), 3f))
            g.DrawEllipse(ring, iconRect.X - 5, iconRect.Y - 5, iconRect.Width + 10, iconRect.Height + 10);
        if (roundIcon != null) g.DrawImage(roundIcon, iconRect);
        else if (icon != null) g.DrawImage(icon, iconRect);
        using (var pen = new Pen(Color.FromArgb(200, 255, 190, 225), 2f)) g.DrawEllipse(pen, iconRect);

        // title with soft glow
        using (var f = new Font("Segoe UI Semibold", 32f, FontStyle.Regular, GraphicsUnit.Pixel))
        {
            for (int i = 3; i >= 1; i--)
                using (var br = new SolidBrush(Color.FromArgb(24, 255, 140, 200)))
                    g.DrawString(appName, f, br, 200 - i, 92 - i);
            using (var br = new SolidBrush(Color.FromArgb(255, 226, 242))) g.DrawString(appName, f, br, 200, 92);
        }
        using (var f = new Font("Segoe UI", 15f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (var br = new SolidBrush(Muted))
            g.DrawString(version.Length > 0 ? "Version " + version : "", f, br, 203, 140);
        using (var f = new Font("Segoe UI", 13f, FontStyle.Italic, GraphicsUnit.Pixel))
        using (var br = new SolidBrush(Color.FromArgb(200, 255, 190, 225)))
            g.DrawString(german ? "dein Companion wartet schon  ♡" : "your companion is waiting  ♡", f, br, 203, 166);

        // progress bar
        var track = new Rectangle(44, 268, Width - 88, 14);
        using (var br = new SolidBrush(Color.FromArgb(70, 255, 255, 255)))
        using (var path = RoundedRect(track, 7)) g.FillPath(br, path);
        int w = (int)(track.Width * Math.Max(0, Math.Min(100, shown)) / 100.0);
        if (w > 8)
        {
            var fill = new Rectangle(track.X, track.Y, w, track.Height);
            using (var path = RoundedRect(fill, 7))
            using (var br = new LinearGradientBrush(fill, Color.FromArgb(255, 150, 205), Color.FromArgb(190, 140, 255), 0f))
            {
                g.FillPath(br, path);
                var st = g.Save();
                g.SetClip(path);
                float sx = fill.X + ((clock * 140f) % (fill.Width + 120f)) - 60f;
                using (var shine = new LinearGradientBrush(new RectangleF(sx - 30, 0, 60, 1), Color.FromArgb(0, 255, 255, 255), Color.FromArgb(120, 255, 255, 255), 0f))
                {
                    var cb = new ColorBlend(3);
                    cb.Colors = new[] { Color.FromArgb(0, 255, 255, 255), Color.FromArgb(140, 255, 255, 255), Color.FromArgb(0, 255, 255, 255) };
                    cb.Positions = new[] { 0f, 0.5f, 1f };
                    shine.InterpolationColors = cb;
                    g.FillRectangle(shine, sx - 30, track.Y, 60, track.Height);
                }
                g.Restore(st);
            }
        }

        // sparkle trail + mascot
        foreach (var s in sparks)
        {
            int alpha = (int)(Math.Max(0f, Math.Min(1f, s.Life)) * 230);
            using (var br = new SolidBrush(Color.FromArgb(alpha, 255, 200, 230)))
            using (var sp = (s.Size > 4f) ? HeartPath(s.X, s.Y, s.Size * 0.9f) : StarPath(s.X, s.Y, s.Size))
                g.FillPath(br, sp);
        }
        DrawMascot(g, MascotX(), 258, shown >= 99.0);

        // texts
        using (var f = new Font("Segoe UI", 14f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (var br = new SolidBrush(Muted))
        {
            int dots = (int)(clock * 2.5f) % 4;
            string label = StageText() + (shown >= 99 ? "" : new string('.', dots));
            g.DrawString(label, f, br, 44, 296);
            string pct = ((int)Math.Round(shown)) + " %";
            var size = g.MeasureString(pct, f);
            g.DrawString(pct, f, br, Width - 44 - size.Width, 296);
        }

        // falling petals on top of everything
        foreach (var p in petals)
        {
            var st = g.Save();
            g.TranslateTransform(p.X, p.Y);
            g.RotateTransform(p.Rot);
            g.ScaleTransform(1f, 0.55f + 0.45f * (float)Math.Abs(Math.Cos(clock * 1.3f + p.Phase)));
            using (var path = PetalPath(p.Size))
            using (var br = new SolidBrush(Color.FromArgb((int)(p.Alpha * 255), 255, 176, 214)))
            using (var edge = new Pen(Color.FromArgb((int)(p.Alpha * 140), 255, 230, 242), 0.8f))
            {
                g.FillPath(br, path);
                g.DrawPath(edge, path);
            }
            g.Restore(st);
        }

        // soft frame
        using (var pen = new Pen(Color.FromArgb(90, 255, 170, 214), 1.6f))
        using (var path = RoundedRect(new Rectangle(1, 1, Width - 3, Height - 3), 21)) g.DrawPath(pen, path);
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        base.OnFormClosed(e);
        // the program keeps running on its own; only a failed start leaves nothing behind
        if (failed && proc != null && !proc.HasExited)
        {
            try { proc.Kill(); } catch { }
        }
    }
}
