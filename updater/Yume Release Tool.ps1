# Yume Release Tool - builds a clean setup / update exe from the MAIN working folder.
# The original folder is only read; everything happens in a temporary copy. Start via "Yume Release Tool.bat".
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

public static class Msg
{
    public static bool Quiet = false;
    public static string Last = "";
    public static DialogResult Show(string text, string caption)
    {
        if (Quiet) { Last += text + "\n"; return DialogResult.No; }
        return MessageBox.Show(text, caption);
    }
    public static DialogResult Show(string text, string caption, MessageBoxButtons b, MessageBoxIcon i)
    {
        if (Quiet) { Last += text + "\n"; return DialogResult.No; }
        return MessageBox.Show(text, caption, b, i);
    }
}

public static class YumeDraw
{
    public static GraphicsPath Round(RectangleF r, float radius)
    {
        GraphicsPath p = new GraphicsPath();
        float d = radius * 2;
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }
}

public class YumeHeader : Panel
{
    class Petal { public float X, Y, S, V, Ph, Rot, Sp; }
    List<Petal> petals = new List<Petal>();
    Random rnd = new Random(4);
    System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    float clock;
    public Image Logo;
    public string Title = "", Subtitle = "";

    public YumeHeader()
    {
        DoubleBuffered = true;
        SetStyle(ControlStyles.ResizeRedraw, true);
        for (int i = 0; i < 16; i++) petals.Add(NewPetal(true));
        timer.Interval = 40;
        timer.Tick += delegate
        {
            clock += 0.04f;
            foreach (Petal p in petals) { p.Y += p.V; p.X += (float)Math.Sin(clock + p.Ph) * 0.5f + 0.25f; p.Rot += p.Sp; }
            for (int i = 0; i < petals.Count; i++) if (petals[i].Y > Height + 10 || petals[i].X > Width + 20) petals[i] = NewPetal(false);
            Invalidate();
        };
        timer.Start();
    }

    Petal NewPetal(bool anywhere)
    {
        Petal p = new Petal();
        p.X = (float)rnd.NextDouble() * 900; p.Y = anywhere ? (float)rnd.NextDouble() * 100 : -10;
        p.S = 3.5f + (float)rnd.NextDouble() * 4.5f; p.V = 0.35f + (float)rnd.NextDouble() * 0.7f;
        p.Ph = (float)rnd.NextDouble() * 6.28f; p.Rot = (float)rnd.NextDouble() * 360; p.Sp = -3 + (float)rnd.NextDouble() * 6;
        return p;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        Rectangle rc = ClientRectangle;
        using (LinearGradientBrush br = new LinearGradientBrush(rc, Color.FromArgb(34, 20, 56), Color.FromArgb(98, 44, 96), 0f)) g.FillRectangle(br, rc);
        GraphicsPath glowPath = new GraphicsPath();
        glowPath.AddEllipse(Width * 0.55f, -60, Width * 0.6f, 200);
        using (PathGradientBrush pg = new PathGradientBrush(glowPath))
        {
            pg.CenterColor = Color.FromArgb(80, 255, 150, 205);
            pg.SurroundColors = new Color[] { Color.FromArgb(0, 255, 150, 205) };
            g.FillPath(pg, glowPath);
        }
        foreach (Petal p in petals)
        {
            GraphicsState st = g.Save();
            g.TranslateTransform(p.X, p.Y); g.RotateTransform(p.Rot);
            using (GraphicsPath path = new GraphicsPath())
            {
                path.AddBezier(0, -p.S, p.S * 0.95f, -p.S * 0.7f, p.S * 0.8f, p.S * 0.7f, 0, p.S);
                path.AddBezier(0, p.S, -p.S * 0.8f, p.S * 0.7f, -p.S * 0.95f, -p.S * 0.7f, 0, -p.S);
                using (SolidBrush b = new SolidBrush(Color.FromArgb(120, 255, 176, 214))) g.FillPath(b, path);
            }
            g.Restore(st);
        }
        int x = 26;
        if (Logo != null)
        {
            Rectangle lr = new Rectangle(x, 14, 64, 64);
            using (GraphicsPath cp = new GraphicsPath())
            {
                cp.AddEllipse(lr);
                GraphicsState st = g.Save();
                g.SetClip(cp);
                int side = Math.Min(Logo.Width, Logo.Height);
                int inset = (int)(side * 0.06);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(Logo, lr, new Rectangle(inset, inset, side - 2 * inset, side - 2 * inset), GraphicsUnit.Pixel);
                g.Restore(st);
            }
            using (Pen pen = new Pen(Color.FromArgb(200, 255, 190, 225), 2f)) g.DrawEllipse(pen, lr);
            x = 106;
        }
        using (Font f = new Font("Segoe UI Semibold", 20f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (SolidBrush b = new SolidBrush(Color.FromArgb(255, 226, 242))) g.DrawString(Title, f, b, x, 20);
        using (Font f = new Font("Segoe UI", 13f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (SolidBrush b = new SolidBrush(Color.FromArgb(214, 190, 224))) g.DrawString(Subtitle, f, b, x + 1, 52);
        using (Pen pen = new Pen(Color.FromArgb(90, 255, 160, 210), 1f)) g.DrawLine(pen, 0, Height - 1, Width, Height - 1);
    }

    protected override void Dispose(bool disposing) { if (disposing) timer.Dispose(); base.Dispose(disposing); }
}

public class YumeCard : Panel
{
    public string Title = "";
    public YumeCard() { DoubleBuffered = true; SetStyle(ControlStyles.ResizeRedraw, true); BackColor = Color.Transparent; }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        RectangleF r = new RectangleF(0.5f, 0.5f, Width - 2, Height - 2);
        using (GraphicsPath p = YumeDraw.Round(r, 14))
        {
            using (SolidBrush b = new SolidBrush(Color.FromArgb(36, 26, 54))) g.FillPath(b, p);
            using (Pen pen = new Pen(Color.FromArgb(70, 255, 143, 199), 1f)) g.DrawPath(pen, p);
        }
        using (Font f = new Font("Segoe UI Semibold", 11f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (SolidBrush b = new SolidBrush(Color.FromArgb(182, 156, 255))) g.DrawString(Title.ToUpper(), f, b, 16, 10);
    }
}

public class RoundButton : Button
{
    public Color Fill = Color.FromArgb(255, 143, 199);
    public Color TextColor = Color.FromArgb(30, 16, 36);
    public bool Ghost = false;
    bool hot;
    public RoundButton()
    {
        FlatStyle = FlatStyle.Flat; FlatAppearance.BorderSize = 0;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
        Cursor = Cursors.Hand; Font = new Font("Segoe UI Semibold", 9.5f);
    }
    protected override void OnMouseEnter(EventArgs e) { hot = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hot = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        if (Parent != null) g.Clear(Parent.BackColor == Color.Transparent ? Color.FromArgb(36, 26, 54) : Parent.BackColor);
        RectangleF r = new RectangleF(0.5f, 0.5f, Width - 2, Height - 2);
        using (GraphicsPath p = YumeDraw.Round(r, Height / 2.4f))
        {
            Color c = Enabled ? Fill : Color.FromArgb(70, 60, 80);
            if (Ghost)
            {
                using (SolidBrush b = new SolidBrush(Color.FromArgb(hot ? 60 : 28, 255, 143, 199))) g.FillPath(b, p);
                using (Pen pen = new Pen(Color.FromArgb(Enabled ? 150 : 60, 255, 143, 199), 1.2f)) g.DrawPath(pen, p);
            }
            else
            {
                Color top = hot ? ControlPaint.Light(c, 0.25f) : c;
                using (LinearGradientBrush b = new LinearGradientBrush(new RectangleF(0, 0, Width, Height), top, ControlPaint.Dark(top, 0.08f), 90f)) g.FillPath(b, p);
            }
        }
        Color tc = Ghost ? Color.FromArgb(Enabled ? 245 : 120, 240, 230, 250) : (Enabled ? TextColor : Color.FromArgb(150, 140, 160));
        TextRenderer.DrawText(g, Text, Font, ClientRectangle, tc, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
    }
}

public class YumeBar : Control
{
    public int Value = 0;
    public bool Busy = false;
    float phase;
    System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    public YumeBar()
    {
        DoubleBuffered = true; Height = 12;
        timer.Interval = 40; timer.Tick += delegate { phase += 0.03f; if (Busy) Invalidate(); };
        timer.Start();
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        if (Parent != null) g.Clear(Parent.BackColor);
        RectangleF r = new RectangleF(0, 0, Width - 1, Height - 1);
        using (GraphicsPath p = YumeDraw.Round(r, Height / 2f))
        using (SolidBrush b = new SolidBrush(Color.FromArgb(60, 255, 255, 255))) g.FillPath(b, p);
        float w = (Width - 1) * Math.Max(0, Math.Min(100, Value)) / 100f;
        if (w > Height)
        {
            RectangleF fr = new RectangleF(0, 0, w, Height - 1);
            using (GraphicsPath p = YumeDraw.Round(fr, Height / 2f))
            using (LinearGradientBrush b = new LinearGradientBrush(fr, Color.FromArgb(255, 150, 205), Color.FromArgb(190, 140, 255), 0f))
            {
                g.FillPath(b, p);
                if (Busy)
                {
                    GraphicsState st = g.Save();
                    g.SetClip(p);
                    float sx = (phase * 160f) % (w + 120f) - 60f;
                    using (LinearGradientBrush sh = new LinearGradientBrush(new RectangleF(sx - 30, 0, 60, 1), Color.FromArgb(0, 255, 255, 255), Color.FromArgb(0, 255, 255, 255), 0f))
                    {
                        ColorBlend cb = new ColorBlend(3);
                        cb.Colors = new Color[] { Color.FromArgb(0, 255, 255, 255), Color.FromArgb(150, 255, 255, 255), Color.FromArgb(0, 255, 255, 255) };
                        cb.Positions = new float[] { 0f, 0.5f, 1f };
                        sh.InterpolationColors = cb;
                        g.FillRectangle(sh, sx - 30, 0, 60, Height);
                    }
                    g.Restore(st);
                }
            }
        }
    }
    protected override void Dispose(bool disposing) { if (disposing) timer.Dispose(); base.Dispose(disposing); }
}
'@

$Here      = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildPs1  = Join-Path $Here 'Yume Build.ps1'
$DoctorPs1 = Join-Path $Here 'Yume Doctor.ps1'
# per-user data (always writable, also when the tool is installed for all users)
$DataDir   = Join-Path $env:APPDATA 'Yume Updater'
$LogDir    = Join-Path $DataDir 'logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$SettingsFile = Join-Path $DataDir 'updater_settings.json'
$oldSettings = Join-Path $Here 'updater_settings.json'
if (-not (Test-Path $SettingsFile) -and (Test-Path $oldSettings)) { Copy-Item $oldSettings $SettingsFile -Force }
$script:LogFile = Join-Path $LogDir 'latest.log'
$StageDir  = Join-Path $env:USERPROFILE 'YumeStage'
$DefSource = 'C:\Pfad\zu\Yume-Companion'
$DefOut    = 'C:\Pfad\zu\Ausgabe'
if (-not (Test-Path $DefSource)) { $DefSource = '' }
if (-not (Test-Path (Split-Path $DefOut -Parent))) { $DefOut = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Yume EXE' }

function Find-Iscc {
    foreach ($p in @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'), (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'), (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'))) { if (Test-Path $p) { return $p } }
    return $null
}

# ---------------------------------------------------------------- settings (remembered between runs)
$S = @{ source = $DefSource; outdir = $DefOut; mode = 'Update'; channel = 'Stabil'; beta = 1; verify = @(1, 1, 0, 0, 0); launcher = $false; deletecopy = $true; patchver = $true; doctor = $true }
try { if (Test-Path $SettingsFile) { $loaded = Get-Content $SettingsFile -Raw | ConvertFrom-Json; foreach ($p in $loaded.PSObject.Properties) { $S[$p.Name] = $p.Value } } } catch {}
function Save-Settings {
    if ($script:TestMode) { return }
    try {
        $o = [ordered]@{ source = $tbSrc.Text; outdir = $tbOut.Text; mode = $(if ($rbUpd.Checked) { 'Update' } else { 'Full' }); channel = $cbChan.SelectedItem; beta = [int]$nuBeta.Value
            verify = @([int]$cbV1.Checked, [int]$cbV2.Checked, [int]$cbV3.Checked, [int]$cbV4.Checked, [int]$cbV5.Checked); launcher = $cbLaunch.Checked; deletecopy = $cbDelete.Checked; patchver = $cbPatch.Checked; doctor = $cbDoctor.Checked }
        $o | ConvertTo-Json | Set-Content $SettingsFile -Encoding UTF8
    } catch {}
}

# ---------------------------------------------------------------- colours / helpers
$cBg = [Drawing.Color]::FromArgb(21, 16, 31); $cText = [Drawing.Color]::FromArgb(243, 233, 247); $cMuted = [Drawing.Color]::FromArgb(185, 169, 201)
$cField = [Drawing.Color]::FromArgb(26, 19, 40); $cPink = [Drawing.Color]::FromArgb(255, 143, 199)
$fontUi = New-Object Drawing.Font('Segoe UI', 9.5)

$form = New-Object Windows.Forms.Form
$form.Text = 'Yume Release Tool'
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object Drawing.Size(760, 956)
$form.BackColor = $cBg; $form.ForeColor = $cText; $form.Font = $fontUi
$form.FormBorderStyle = 'FixedSingle'; $form.MaximizeBox = $false

function New-Label($parent, $text, $x, $y, $color) { $l = New-Object Windows.Forms.Label; $l.Text = $text; $l.Left = $x; $l.Top = $y; $l.AutoSize = $true; $l.BackColor = [Drawing.Color]::Transparent; $l.ForeColor = $(if ($color) { $color } else { $cMuted }); $parent.Controls.Add($l); $l }
function New-Text($parent, $x, $y, $w, $text) { $t = New-Object Windows.Forms.TextBox; $t.Left = $x; $t.Top = $y; $t.Width = $w; $t.Text = $text; $t.BackColor = $cField; $t.ForeColor = $cText; $t.BorderStyle = 'FixedSingle'; $parent.Controls.Add($t); $t }
function New-Btn($parent, $text, $x, $y, $w, $h, $ghost) { $b = New-Object RoundButton; $b.Text = $text; $b.Left = $x; $b.Top = $y; $b.Width = $w; $b.Height = $h; $b.Ghost = [bool]$ghost; $parent.Controls.Add($b); $b }
function New-Check($parent, $text, $x, $y, $w, $checked) { $c = New-Object Windows.Forms.CheckBox; $c.Text = $text; $c.Left = $x; $c.Top = $y; $c.Width = $w; $c.Checked = [bool]$checked; $c.BackColor = [Drawing.Color]::Transparent; $c.ForeColor = $cText; $c.FlatStyle = 'Standard'; $parent.Controls.Add($c); $c }
function New-Card($title, $y, $h) { $c = New-Object YumeCard; $c.Title = $title; $c.Left = 20; $c.Top = $y; $c.Width = 720; $c.Height = $h; $form.Controls.Add($c); $c }

# ---------------------------------------------------------------- header
$header = New-Object YumeHeader
$header.Left = 0; $header.Top = 0; $header.Width = 760; $header.Height = 90
$header.Title = 'Yume Release Tool'; $header.Subtitle = 'Aus dem MAIN-Ordner ein sauberes Setup bauen - das Original bleibt unberuehrt'
try {
    $img = Join-Path $S.source 'assets\custom_branding\app_icon_path.png'
    if (-not (Test-Path $img)) { $img = Join-Path $Here 'installer_build\app_icon.png' }
    if (Test-Path $img) { $bytes = [IO.File]::ReadAllBytes($img); $ms = New-Object IO.MemoryStream(, $bytes); $header.Logo = [Drawing.Image]::FromStream($ms) }
} catch {}
$form.Controls.Add($header)

# ---------------------------------------------------------------- card: folders
$cardF = New-Card 'Ordner' 102 134
New-Label $cardF 'Arbeitsordner (wird nur gelesen, nie veraendert)' 16 32 $cMuted | Out-Null
$tbSrc = New-Text $cardF 16 52 560 $S.source
$btSrc = New-Btn $cardF 'Suchen' 590 49 114 28 $true
New-Label $cardF 'Ausgabeordner fuer die fertige Exe' 16 82 $cMuted | Out-Null
$tbOut = New-Text $cardF 16 102 460 $S.outdir
$btOutB = New-Btn $cardF 'Suchen' 486 99 100 28 $true
$btOutO = New-Btn $cardF 'Oeffnen' 596 99 108 28 $true

# ---------------------------------------------------------------- card: version
$cardV = New-Card 'Version & Art' 246 118
New-Label $cardV 'Aktuell:' 16 34 $cMuted | Out-Null
$lbCur = New-Label $cardV '-' 70 34 $cPink; $lbCur.Font = New-Object Drawing.Font('Segoe UI', 9.5, [Drawing.FontStyle]::Bold)
New-Label $cardV 'Neue Version:' 190 34 $cMuted | Out-Null
$tbVer = New-Text $cardV 280 31 90 ''
New-Label $cardV 'Kanal:' 392 34 $cMuted | Out-Null
$cbChan = New-Object Windows.Forms.ComboBox; $cbChan.Left = 440; $cbChan.Top = 31; $cbChan.Width = 100; $cbChan.DropDownStyle = 'DropDownList'; $cbChan.FlatStyle = 'Flat'; $cbChan.BackColor = $cField; $cbChan.ForeColor = $cText
[void]$cbChan.Items.AddRange(@('Stabil', 'Beta', 'RC')); $cbChan.SelectedItem = $(if ($S.channel) { $S.channel } else { 'Stabil' }); $cardV.Controls.Add($cbChan)
New-Label $cardV 'Nr.:' 556 34 $cMuted | Out-Null
$nuBeta = New-Object Windows.Forms.NumericUpDown; $nuBeta.Left = 590; $nuBeta.Top = 31; $nuBeta.Width = 56; $nuBeta.Minimum = 1; $nuBeta.Maximum = 99; $nuBeta.Value = [Math]::Max(1, [int]$S.beta); $nuBeta.BackColor = $cField; $nuBeta.ForeColor = $cText; $cardV.Controls.Add($nuBeta)
$rbUpd = New-Object Windows.Forms.RadioButton; $rbUpd.Text = 'Nur Update - klein, Programmcode ueber die bestehende Installation (Umgebung, Modelle, Einstellungen bleiben)'; $rbUpd.Left = 14; $rbUpd.Top = 62; $rbUpd.Width = 690; $rbUpd.BackColor = [Drawing.Color]::Transparent; $rbUpd.ForeColor = $cText; $cardV.Controls.Add($rbUpd)
$rbFull = New-Object Windows.Forms.RadioButton; $rbFull.Text = 'Voll-Installer - komplette Neuinstallation mit Komponenten-Auswahl (ca. 2 GB)'; $rbFull.Left = 14; $rbFull.Top = 86; $rbFull.Width = 690; $rbFull.BackColor = [Drawing.Color]::Transparent; $rbFull.ForeColor = $cText; $cardV.Controls.Add($rbFull)
if ($S.mode -eq 'Full') { $rbFull.Checked = $true } else { $rbUpd.Checked = $true }

# ---------------------------------------------------------------- card: verification
$cardP = New-Card 'Pruefung - stellt sicher, dass die Exe wirklich funktioniert' 374 164
$cbV1 = New-Check $cardP 'Basis-Pruefung vor dem Bau: Standardzustand, nichts Persoenliches, Syntax, Importe (bricht bei Fehlern ab)' 14 30 690 ([bool]$S.verify[0])
$cbV2 = New-Check $cardP 'Start-Test: Programm startet (ohne Fenster), alle Seiten werden gezeichnet' 14 56 690 ([bool]$S.verify[1])
$cbV3 = New-Check $cardP 'Installationstest: Setup still in einen Testordner installieren (eigene AppId, danach geloescht)' 14 82 690 ([bool]$S.verify[2])
$cbV4 = New-Check $cardP 'Mini-KI-Test: kleines Testmodell (einmalig ca. 470 MB) ueber mitgelieferte llama.cpp und eigenen Provider' 14 108 690 ([bool]$S.verify[3])
$cbV5 = New-Check $cardP 'Praxistest (nur Voll-Installer): ECHTE Installation inkl. installer.bat, danach Import- und Start-Test - 15-30 Min., laedt mehrere GB' 14 134 690 ([bool]$S.verify[4])

# ---------------------------------------------------------------- options + action
$cbPatch = New-Check $form 'Versionsnummer in der Kopie setzen' 26 548 230 ([bool]$S.patchver)
$cbLaunch = New-Check $form 'Launcher neu kompilieren' 262 548 190 ([bool]$S.launcher)
$cbDelete = New-Check $form 'Arbeitskopie danach loeschen' 458 548 220 ([bool]$S.deletecopy)
$cbDoctor = New-Check $form 'Bei Fehlern automatisch analysieren (Regeln; lokale KI nur wenn ein starkes Modell installiert ist)' 26 572 700 ([bool]$S.doctor)
$lbName = New-Object Windows.Forms.Label; $lbName.Left = 26; $lbName.Top = 602; $lbName.AutoSize = $true; $lbName.ForeColor = $cPink; $lbName.BackColor = [Drawing.Color]::Transparent; $form.Controls.Add($lbName)
$btInno = New-Btn $form 'Inno Setup installieren' 520 596 220 28 $true
$btInno.Visible = $false
$btBuild = New-Btn $form 'Scannen + Setup erstellen' 24 630 232 44 $false
$btBuild.Font = New-Object Drawing.Font('Segoe UI Semibold', 10.5)
$bar = New-Object YumeBar; $bar.Left = 276; $bar.Top = 636; $bar.Width = 462; $bar.Height = 12; $form.Controls.Add($bar)
$lbStep = New-Object Windows.Forms.Label; $lbStep.Left = 276; $lbStep.Top = 654; $lbStep.Width = 462; $lbStep.Height = 20; $lbStep.ForeColor = $cMuted; $lbStep.BackColor = [Drawing.Color]::Transparent; $lbStep.Text = 'Bereit.'; $form.Controls.Add($lbStep)

# ---------------------------------------------------------------- log (always visible, also saved to a file)
New-Label $form 'PROTOKOLL' 24 688 ([Drawing.Color]::FromArgb(182, 156, 255)) | Out-Null
$lbLogPath = New-Object Windows.Forms.Label; $lbLogPath.Left = 100; $lbLogPath.Top = 689; $lbLogPath.Width = 250; $lbLogPath.Height = 16; $lbLogPath.ForeColor = [Drawing.Color]::FromArgb(130, 115, 150); $lbLogPath.BackColor = [Drawing.Color]::Transparent
$lbLogPath.Font = New-Object Drawing.Font('Segoe UI', 8); $lbLogPath.Text = $LogDir; $form.Controls.Add($lbLogPath)
$btLogOpen = New-Btn $form 'Log oeffnen' 356 682 92 26 $true
$btLogDir = New-Btn $form 'Ordner' 452 682 72 26 $true
$btLogCopy = New-Btn $form 'Kopieren' 528 682 80 26 $true
$btDoctor = New-Btn $form 'Fehler analysieren' 612 682 128 26 $true
$tbLog = New-Object Windows.Forms.RichTextBox
$tbLog.Left = 20; $tbLog.Top = 714; $tbLog.Width = 720; $tbLog.Height = 214
$tbLog.ReadOnly = $true; $tbLog.BackColor = [Drawing.Color]::FromArgb(14, 9, 22); $tbLog.ForeColor = $cMuted; $tbLog.BorderStyle = 'None'
$tbLog.Font = New-Object Drawing.Font('Consolas', 9); $tbLog.DetectUrls = $false
$form.Controls.Add($tbLog)

# ---------------------------------------------------------------- logic
function Full-Version {
    $v = $tbVer.Text.Trim()
    switch ($cbChan.SelectedItem) { 'Beta' { $v += "-beta$($nuBeta.Value)" } 'RC' { $v += "-rc$($nuBeta.Value)" } }
    return $v
}
function Refresh-Name {
    $kind = if ($rbUpd.Checked) { 'Update' } else { 'Setup' }
    $lbName.Text = "Ergebnis: Yume-Companion-$kind-$(Full-Version).exe"
}
function Refresh-Current {
    $vf = Join-Path $tbSrc.Text 'VERSION.txt'
    $lbCur.Text = if (Test-Path $vf) { (Get-Content $vf -Raw).Trim() } else { '?' }
    if (-not $tbVer.Text -and $lbCur.Text -match '^(\d+)\.(\d+)\.(\d+)') { $tbVer.Text = "$($Matches[1]).$($Matches[2]).$([int]$Matches[3] + 1)" }
}
function Add-LogLine($line) {
    $color = $cMuted; $bold = $false
    if ($line -match '^\s*OK\b') { $color = [Drawing.Color]::FromArgb(110, 231, 160) }
    elseif ($line -match '^\s*FEHLER|PRUEFUNG.*FEHLER|Problem\(e\)') { $color = [Drawing.Color]::FromArgb(255, 120, 140); $bold = $true }
    elseif ($line -match '^\s*HINWEIS') { $color = [Drawing.Color]::FromArgb(251, 191, 36) }
    elseif ($line -match '^===') { $color = $cPink; $bold = $true }
    elseif ($line -match '^FERTIG|ALLES IN ORDNUNG') { $color = [Drawing.Color]::FromArgb(110, 231, 160); $bold = $true }
    elseif ($line -match '^---') { $color = [Drawing.Color]::FromArgb(182, 156, 255) }
    elseif ($line -match '^\[Analyse\]|^\[KI\]|^\[Fix\]') { $color = [Drawing.Color]::FromArgb(130, 205, 255); $bold = $true }
    $tbLog.SelectionStart = $tbLog.TextLength; $tbLog.SelectionLength = 0
    $tbLog.SelectionColor = $color
    $tbLog.SelectionFont = New-Object Drawing.Font('Consolas', 9, $(if ($bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }))
    $tbLog.AppendText($line + "`r`n")
    $tbLog.ScrollBars = 'Vertical'
    $tbLog.ScrollToCaret()
}
function Log-App($text) {
    # lines written by the tool itself (also persisted in the run log)
    Add-LogLine $text
    try { Add-Content -Path $script:LogFile -Value $text -Encoding UTF8 } catch {}
}
$script:progressMap = @(
    @('1/5', 6), @('2/5', 14), @('3/5', 24), @('4/5', 36), @('Pruefung der sauberen Kopie', 52), @('5/5', 64), @('Pruefung der gebauten Exe', 84))
function Update-Progress($line) {
    if ($line -match '^===') {
        foreach ($m in $script:progressMap) { if ($line.Contains($m[0])) { $bar.Value = $m[1]; $lbStep.Text = ($line -replace '^=+\s*', ''); break } }
    } elseif ($line -match '^FERTIG') { $bar.Value = [Math]::Max($bar.Value, 80); $lbStep.Text = 'Exe gebaut' }
}
$cbChan.Add_SelectedIndexChanged({ $nuBeta.Enabled = ($cbChan.SelectedItem -ne 'Stabil'); Refresh-Name })
$nuBeta.Enabled = ($cbChan.SelectedItem -ne 'Stabil')
$tbVer.Add_TextChanged({ Refresh-Name }); $nuBeta.Add_ValueChanged({ Refresh-Name }); $rbUpd.Add_CheckedChanged({ Refresh-Name })
$tbSrc.Add_TextChanged({ Refresh-Current })
$btSrc.Add_Click({ $d = New-Object Windows.Forms.FolderBrowserDialog; $d.SelectedPath = $tbSrc.Text; if ($d.ShowDialog() -eq 'OK') { $tbSrc.Text = $d.SelectedPath } })
$btOutB.Add_Click({ $d = New-Object Windows.Forms.FolderBrowserDialog; $d.Description = 'Ausgabeordner fuer die fertige Exe'; $d.SelectedPath = $tbOut.Text; $d.ShowNewFolderButton = $true; if ($d.ShowDialog() -eq 'OK') { $tbOut.Text = $d.SelectedPath } })
$btOutO.Add_Click({ $p = $tbOut.Text.Trim(); if ($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }; Start-Process explorer.exe $p } })
$btLogOpen.Add_Click({ if (Test-Path $script:LogFile) { Start-Process notepad.exe $script:LogFile } })
$btLogDir.Add_Click({ Start-Process explorer.exe $LogDir })
$btLogCopy.Add_Click({ if ($tbLog.TextLength -gt 0) { [Windows.Forms.Clipboard]::SetText($tbLog.Text); $lbStep.Text = 'Protokoll in die Zwischenablage kopiert.' } })

# ---------------------------------------------------------------- Inno Setup check
function Refresh-Inno {
    $script:IsccPath = Find-Iscc
    $btInno.Visible = (-not $script:IsccPath)
    $btBuild.Enabled = [bool]$script:IsccPath
    if (-not $script:IsccPath) { $lbStep.Text = 'Inno Setup 6 fehlt - bitte rechts installieren.' }
}
$btInno.Add_Click({
    $r = [Msg]::Show("Inno Setup 6 (der kostenlose Setup-Compiler) wird per winget nur fuer deinen Benutzer installiert. Fortfahren?", 'Yume Release Tool', 'YesNo', 'Question')
    if ($r -ne 'Yes') { return }
    $btInno.Enabled = $false; $lbStep.Text = 'Installiere Inno Setup ...'
    Log-App '[Fix] winget install JRSoftware.InnoSetup (Benutzer-Installation) ...'
    $p = Start-Process -FilePath 'winget.exe' -ArgumentList 'install', '--id', 'JRSoftware.InnoSetup', '-e', '--scope', 'user', '--accept-package-agreements', '--accept-source-agreements', '--silent' -WindowStyle Hidden -PassThru -Wait
    Log-App "[Fix] winget beendet (Code $($p.ExitCode))"
    $btInno.Enabled = $true
    Refresh-Inno
    if ($script:IsccPath) { $lbStep.Text = 'Inno Setup installiert.' }
})

# ---------------------------------------------------------------- doctor (error analysis) + safe fixes
$script:doctorProc = $null; $script:doctorJson = $null
function Start-Doctor {
    if ($script:doctorProc -and -not $script:doctorProc.HasExited) { return }
    $script:doctorJson = Join-Path $DataDir 'doctor_last.json'
    Remove-Item $script:doctorJson -ErrorAction SilentlyContinue
    $lbStep.Text = 'Analysiere den Fehler ... (lokale KI nur, wenn ein starkes Modell installiert ist)'
    $bar.Busy = $true
    $btDoctor.Enabled = $false
    $args2 = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$DoctorPs1`"", '-LogFile', "`"$script:LogFile`"", '-Source', "`"$($tbSrc.Text.Trim())`"", '-OutJson', "`"$script:doctorJson`"", '-UseAI')
    $script:doctorProc = Start-Process -FilePath 'powershell.exe' -ArgumentList $args2 -WindowStyle Hidden -PassThru
    $doctorTimer.Start()
}
function Stop-Leftovers {
    $dirs = @($StageDir, (Join-Path $env:USERPROFILE 'YumeVerify'))
    foreach ($proc in Get-Process -ErrorAction SilentlyContinue) {
        try {
            $path = $proc.Path
            if (-not $path) { continue }
            if (($dirs | Where-Object { $path.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }) -or ($proc.ProcessName -eq 'llama-server' -and $path -like '*Yume*')) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue; Log-App "[Fix] beendet: $($proc.ProcessName) ($($proc.Id))" }
        } catch {}
    }
}
function Remove-Dirs { foreach ($d in @($StageDir, (Join-Path $env:USERPROFILE 'YumeVerify'))) { if (Test-Path $d) { & cmd.exe /c rd /s /q "`"$d`"" | Out-Null; Log-App "[Fix] geloescht: $d" } } }
function Apply-Fix($id) {
    switch ($id) {
        'retry' { }
        'clear_stage' { Remove-Dirs }
        'kill_leftovers' { Stop-Leftovers; Start-Sleep -Milliseconds 800; Remove-Dirs }
        'install_inno' { $btInno.PerformClick(); return }
        'skip_ai' { $cbV4.Checked = $false; Log-App '[Fix] Mini-KI-Test fuer diesen Lauf ausgeschaltet.' }
        'skip_smoke' { $cbV2.Checked = $false; Log-App '[Fix] Start-Test fuer diesen Lauf ausgeschaltet.' }
        'skip_install' { $cbV3.Checked = $false; Log-App '[Fix] Installationstest fuer diesen Lauf ausgeschaltet.' }
    }
    $btBuild.PerformClick()
}
function Show-Analysis($res) {
    $dlg = New-Object Windows.Forms.Form
    $dlg.Text = 'Fehleranalyse'; $dlg.StartPosition = 'CenterParent'; $dlg.ClientSize = New-Object Drawing.Size(640, 460); $dlg.BackColor = $cBg; $dlg.ForeColor = $cText; $dlg.Font = $fontUi
    $dlg.FormBorderStyle = 'FixedDialog'; $dlg.MaximizeBox = $false; $dlg.MinimizeBox = $false
    $rt = New-Object Windows.Forms.RichTextBox; $rt.Left = 16; $rt.Top = 16; $rt.Width = 608; $rt.Height = 330; $rt.ReadOnly = $true; $rt.BorderStyle = 'None'
    $rt.BackColor = [Drawing.Color]::FromArgb(14, 9, 22); $rt.ForeColor = $cText; $rt.Font = New-Object Drawing.Font('Segoe UI', 10); $dlg.Controls.Add($rt)
    function Add-Rt($t, $c, $b) { $rt.SelectionStart = $rt.TextLength; $rt.SelectionColor = $c; $rt.SelectionFont = New-Object Drawing.Font('Segoe UI', 10, $(if ($b) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular })); $rt.AppendText($t + "`r`n") }
    Add-Rt 'Was ist schiefgelaufen?' $cPink $true
    if (@($res.hits).Count -eq 0) { Add-Rt 'Keine bekannte Ursache erkannt - die FEHLER-Zeilen im Protokoll nennen den Grund.' $cText $false }
    foreach ($h in @($res.hits)) { Add-Rt ('- ' + $h.explain) $cText $false }
    if ($res.ai.used) {
        Add-Rt '' $cText $false
        Add-Rt ('Lokale KI (' + $res.ai.model + '):') ([Drawing.Color]::FromArgb(130, 205, 255)) $true
        if ($res.ai.cause) { Add-Rt ('Ursache: ' + $res.ai.cause) $cText $false }
        if ($res.ai.solution) { Add-Rt ('Loesung: ' + $res.ai.solution) $cText $false }
    } elseif ($res.ai.note) {
        Add-Rt '' $cText $false
        Add-Rt $res.ai.note $cMuted $false
    }
    $y = 360
    foreach ($f in @($res.fixes)) {
        $b = New-Object RoundButton; $b.Text = 'Anwenden & neu bauen: ' + $f.text; $b.Left = 16; $b.Top = $y; $b.Width = 608; $b.Height = 34
        $fixId = [string]$f.id; $b.Tag = $fixId
        $b.Add_Click({ param($s, $e) $script:chosenFix = [string]$s.Tag; $dlg.Close() })
        $dlg.Controls.Add($b); $y += 40
    }
    $close = New-Object RoundButton; $close.Text = 'Schliessen'; $close.Ghost = $true; $close.Left = 16; $close.Top = $y; $close.Width = 608; $close.Height = 34
    $close.Add_Click({ $dlg.Close() }); $dlg.Controls.Add($close)
    $dlg.ClientSize = New-Object Drawing.Size(640, ($y + 50))
    $script:chosenFix = $null
    [void]$dlg.ShowDialog($form)
    if ($script:chosenFix) { Apply-Fix $script:chosenFix }
}
$doctorTimer = New-Object Windows.Forms.Timer; $doctorTimer.Interval = 800
$doctorTimer.Add_Tick({
    if ($script:doctorProc -and $script:doctorProc.HasExited) {
        $doctorTimer.Stop(); $bar.Busy = $false; $btDoctor.Enabled = $true
        $res = $null
        try { if (Test-Path $script:doctorJson) { $res = Get-Content $script:doctorJson -Raw -Encoding UTF8 | ConvertFrom-Json } } catch {}
        if (-not $res) { $lbStep.Text = 'Analyse nicht moeglich.'; return }
        $lbStep.Text = 'Analyse fertig.'
        Log-App '[Analyse] ----------------------------------------'
        foreach ($h in @($res.hits)) { Log-App ('[Analyse] ' + $h.explain) }
        if ($res.ai.used) { Log-App ('[KI] ' + $res.ai.model); if ($res.ai.cause) { Log-App ('[KI] Ursache: ' + $res.ai.cause) }; if ($res.ai.solution) { Log-App ('[KI] Loesung: ' + $res.ai.solution) } }
        elseif ($res.ai.note) { Log-App ('[Analyse] ' + $res.ai.note) }
        if ($script:TestMode) { Log-App '[Analyse] (Testmodus: Dialog uebersprungen)' } else { Show-Analysis $res }
    }
})
$btDoctor.Add_Click({ if (Test-Path $script:LogFile) { Start-Doctor } else { [Msg]::Show('Es gibt noch kein Protokoll.', 'Yume Release Tool') | Out-Null } })

# ---------------------------------------------------------------- build run
$script:proc = $null
$script:shown = 0
$timer = New-Object Windows.Forms.Timer; $timer.Interval = 600
$timer.Add_Tick({
    $lines = @(Get-Content $script:RunLog -ErrorAction SilentlyContinue)
    if ($lines.Count -gt $script:shown) {
        for ($i = $script:shown; $i -lt $lines.Count; $i++) { Add-LogLine $lines[$i]; Update-Progress $lines[$i] }
        $script:shown = $lines.Count
        try { Copy-Item $script:RunLog $script:LogFile -Force } catch {}
    }
    if ($script:proc -and $script:proc.HasExited) {
        $timer.Stop(); $btBuild.Enabled = $true; $bar.Busy = $false
        try { Copy-Item $script:RunLog $script:LogFile -Force } catch {}
        $done = ($lines | Where-Object { $_ -like 'FERTIG:*' } | Select-Object -Last 1)
        $verdict = ($lines | Where-Object { $_ -like 'PRUEFUNG DER EXE:*' } | Select-Object -Last 1)
        $failed = (-not $done) -or ($script:proc.ExitCode -ne 0)
        if ($done) {
            $bar.Value = 100; $lbStep.Text = $(if ($failed) { 'Exe gebaut - Pruefung meldet Probleme' } else { 'Fertig' })
            Refresh-Current
            $msg = $done + $(if ($verdict) { "`n`n" + $verdict } else { '' }) + "`n`nAusgabeordner oeffnen?"
            $r = [Msg]::Show($msg, 'Yume Release Tool', 'YesNo', $(if ($failed) { 'Warning' } else { 'Information' }))
            if ($r -eq 'Yes') { Start-Process explorer.exe $tbOut.Text.Trim() }
        } else { $lbStep.Text = 'Abgebrochen / fehlgeschlagen' }
        if ($failed -and $cbDoctor.Checked) { Start-Doctor }
        elseif ($failed -and -not $done) { [Msg]::Show('Der Build ist fehlgeschlagen - Details stehen im Protokoll.', 'Yume Release Tool', 'OK', 'Error') | Out-Null }
    }
})

$btBuild.Add_Click({
    $src = $tbSrc.Text.Trim().TrimEnd('\'); $out = $tbOut.Text.Trim().TrimEnd('\')
    if ($tbVer.Text.Trim() -notmatch '^\d+\.\d+(\.\d+)?$') { [Msg]::Show('Version bitte als Zahl eingeben, z.B. 2.5.4', 'Yume Release Tool') | Out-Null; return }
    if (-not (Test-Path (Join-Path $src 'main.py'))) { [Msg]::Show('Im Arbeitsordner wurde main.py nicht gefunden.', 'Yume Release Tool') | Out-Null; return }
    if (-not $out) { [Msg]::Show('Bitte einen Ausgabeordner waehlen.', 'Yume Release Tool') | Out-Null; return }
    if ($out.StartsWith($src, [StringComparison]::OrdinalIgnoreCase)) { [Msg]::Show('Der Ausgabeordner darf nicht im Arbeitsordner liegen - dort wird nichts geschrieben.', 'Yume Release Tool') | Out-Null; return }
    Save-Settings
    $mode = if ($rbUpd.Checked) { 'Update' } else { 'Full' }
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$BuildPs1`"", '-Version', (Full-Version), '-Mode', $mode, '-Source', "`"$src`"", '-OutDir', "`"$out`"")
    if ($cbLaunch.Checked) { $a += '-Launcher' }
    if (-not $cbPatch.Checked) { $a += '-NoPatch' }
    if (-not $cbDelete.Checked) { $a += '-KeepStage' }
    if ($cbV1.Checked) { $a += '-Verify' }
    if ($cbV2.Checked) { $a += '-VerifySmoke' }
    if ($cbV3.Checked) { $a += '-VerifyInstall' }
    if ($cbV4.Checked) { $a += '-VerifyAI' }
    if ($cbV5.Checked -and $mode -eq 'Full') { $a += '-VerifyDeps' }
    # every run gets its own log file (last 20 are kept); latest.log always points at the newest run
    $stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
    $script:RunLog = Join-Path $LogDir "build_$stamp.log"
    $header = @("# Yume Release Tool - Lauf $stamp", "# Version: $(Full-Version)  Modus: $mode  Quelle: $src  Ausgabe: $out", '')
    Set-Content -Path $script:RunLog -Value $header -Encoding UTF8
    Get-ChildItem $LogDir -Filter 'build_*.log' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 20 | Remove-Item -Force -ErrorAction SilentlyContinue
    $tbLog.Clear(); $script:shown = 0; $bar.Value = 2; $bar.Busy = $true; $lbStep.Text = 'Starte ...'
    $lbLogPath.Text = $script:RunLog
    $btBuild.Enabled = $false
    $script:proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "powershell.exe $($a -join ' ') >> `"$script:RunLog`" 2>&1" -WindowStyle Hidden -PassThru
    $timer.Start()
})
$form.Add_FormClosing({ if (-not $script:TestMode) { Save-Settings } })

Refresh-Current; Refresh-Name; Refresh-Inno
Add-LogLine 'Bereit. Der Arbeitsordner wird nur gelesen - alles passiert in einer temporaeren Kopie.'
Add-LogLine "Protokolle: $LogDir"
$script:TestMode = [bool]$env:YUME_UPDATER_TEST
$form.Add_Shown({ $form.ActiveControl = $btBuild })
if ($script:TestMode) {
    [Msg]::Quiet = $true
    $testTimer = New-Object Windows.Forms.Timer; $testTimer.Interval = 1500
    $script:testStage = 0
    $testTimer.Add_Tick({
        if ($script:testStage -eq 0) {
            $script:testStage = 1
            $tbSrc.Text = $env:YUME_TEST_SRC; $tbOut.Text = $env:YUME_TEST_OUT; $tbVer.Text = '9.9'; $cbChan.SelectedItem = 'Stabil'
            $cbV1.Checked = [bool]($env:YUME_TEST_VERIFY -eq '1'); $cbV2.Checked = $false; $cbV3.Checked = $false; $cbV4.Checked = $false; $cbV5.Checked = $false
            $cbDoctor.Checked = $true; $cbDelete.Checked = $true
            $btBuild.PerformClick()
        } elseif ($script:testStage -eq 1 -and $script:proc -and $script:proc.HasExited) {
            $script:testStage = 2     # wait for the doctor (if the build failed)
        } elseif ($script:testStage -eq 2) {
            $doctorRunning = ($script:doctorProc -and -not $script:doctorProc.HasExited)
            if (-not $doctorRunning -and -not $timer.Enabled -and -not $doctorTimer.Enabled) {
                $testTimer.Stop()
                $summary = [ordered]@{ step = $lbStep.Text; exit = $script:proc.ExitCode; runLog = $script:RunLog; latest = (Test-Path $script:LogFile); msg = [Msg]::Last; logLines = $tbLog.Lines.Count; doctorJson = $script:doctorJson }
                $summary | ConvertTo-Json | Set-Content $env:YUME_TEST_RESULT -Encoding UTF8
                $form.Close()
            }
        }
    })
    $testTimer.Start()
}
[void]$form.ShowDialog()
