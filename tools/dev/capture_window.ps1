<#
  Fotografiert das Fenster eines Windows-Programms (z. B. den Yume LLM Server) als PNG.
  Aufruf:  powershell -ExecutionPolicy Bypass -File tools\dev\capture_window.ps1 -Exe "C:\Pfad\YumeLLMServer.exe" -Out bild.png [-Wait 4] [-Clicks "x,y;x,y"] [-Prefix name]
  -Clicks: Mausklicks (relativ zur linken oberen Fensterecke), nach jedem Klick wird ein weiteres Bild "<Prefix>_<n>.png" gespeichert.
#>
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$Wait = 4,
    [string]$Clicks = '',
    [switch]$KeepOpen,
    [switch]$Screen   # Bild vom Bildschirm statt vom Fenster (zeigt auch Dialoge, die ueber dem Fenster liegen)
)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing @'
using System;
using System.Runtime.InteropServices;
using System.Drawing;
public static class Win {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  public static Bitmap Screen(IntPtr h) {
    RECT r; GetWindowRect(h, out r);
    Bitmap bmp = new Bitmap(r.Right - r.Left, r.Bottom - r.Top);
    using (Graphics g = Graphics.FromImage(bmp)) g.CopyFromScreen(r.Left, r.Top, 0, 0, bmp.Size);
    return bmp;
  }
  public static Bitmap Shot(IntPtr h) {
    RECT r; GetWindowRect(h, out r);
    int w = r.Right - r.Left, ht = r.Bottom - r.Top;
    Bitmap bmp = new Bitmap(w, ht);
    using (Graphics g = Graphics.FromImage(bmp)) { IntPtr dc = g.GetHdc(); PrintWindow(h, dc, 2); g.ReleaseHdc(dc); }
    return bmp;
  }
  public static void Click(int x, int y) { SetCursorPos(x, y); mouse_event(2, 0, 0, 0, UIntPtr.Zero); mouse_event(4, 0, 0, 0, UIntPtr.Zero); }
}
'@
$p = Start-Process -FilePath $Exe -PassThru
Start-Sleep -Seconds $Wait
$p.Refresh()
$h = $p.MainWindowHandle
if ($h -eq [IntPtr]::Zero) { Write-Host 'Kein Fenster gefunden.'; if (-not $KeepOpen) { $p.CloseMainWindow() | Out-Null }; exit 1 }
[Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 600
$bmp = if ($Screen) { [Win]::Screen($h) } else { [Win]::Shot($h) }; $bmp.Save($Out, [Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
Write-Host "gespeichert: $Out"
if ($Clicks) {
    $r = New-Object Win+RECT; [Win]::GetWindowRect($h, [ref]$r) | Out-Null
    $n = 0
    foreach ($c in $Clicks.Split(';')) {
        $xy = $c.Split(','); $n++
        [Win]::Click($r.Left + [int]$xy[0], $r.Top + [int]$xy[1])
        Start-Sleep -Milliseconds 1200
        $b2 = if ($Screen) { [Win]::Screen($h) } else { [Win]::Shot($h) }
        $f2 = [IO.Path]::Combine([IO.Path]::GetDirectoryName($Out), ([IO.Path]::GetFileNameWithoutExtension($Out) + "_$n.png"))
        $b2.Save($f2, [Drawing.Imaging.ImageFormat]::Png); $b2.Dispose()
        Write-Host "gespeichert: $f2"
    }
}
if (-not $KeepOpen) { $p.CloseMainWindow() | Out-Null; Start-Sleep 1; if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }


