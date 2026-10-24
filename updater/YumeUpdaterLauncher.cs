// Yume Release Tool launcher: starts the PowerShell GUI without a console window.
// Build: csc /target:winexe /win32icon:installer_build\setup_icon.ico YumeUpdaterLauncher.cs
using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class Program
{
    [STAThread]
    static void Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        string script = Path.Combine(dir, "Yume Release Tool.ps1");
        if (!File.Exists(script))
        {
            MessageBox.Show("Yume Release Tool.ps1 wurde nicht gefunden:\n" + script, "Yume Release Tool", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        string id;
        using (MD5 md5 = MD5.Create())
            id = BitConverter.ToString(md5.ComputeHash(Encoding.UTF8.GetBytes(dir.ToLowerInvariant()))).Replace("-", "");
        bool created;
        using (Mutex mutex = new Mutex(true, "YumeReleaseTool_" + id, out created))
        {
            if (!created) return; // already running
            ProcessStartInfo psi = new ProcessStartInfo("powershell.exe",
                "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File \"" + script + "\"");
            psi.WorkingDirectory = dir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            try
            {
                using (Process p = Process.Start(psi)) { p.WaitForExit(); }
            }
            catch (Exception ex)
            {
                MessageBox.Show("PowerShell konnte nicht gestartet werden:\n" + ex.Message, "Yume Release Tool", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
