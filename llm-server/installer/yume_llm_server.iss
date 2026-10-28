; Yume LLM Server - installer (Inno Setup 6). Build with "Build Yume LLM Server.ps1".

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Yume LLM Server"
#define AppExe  "YumeLLMServer.exe"

[Setup]
AppId={{6F1C8E52-2D4A-4B7E-9A31-5E8B0C47D9A2}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Kreqzxoo
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
VersionInfoCompany=Kreqzxoo
VersionInfoCopyright=Copyright (c) 2026 Kreqzxoo
#ifdef Sign
; code signing: "Build Yume LLM Server.ps1" passes the command (environment variable YUME_SIGN_CMD) as /Syume=...
SignTool=yume
SignedUninstaller=yes
#endif
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
DefaultDirName={autopf}\Yume LLM Server
UsePreviousAppDir=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=Yume-LLM-Server-Setup-{#AppVersion}
SetupIconFile=..\build\yume.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=wizard_large.bmp,wizard_large_2x.bmp
WizardSmallImageFile=wizard_small.bmp,wizard_small_2x.bmp
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; LicenseFile: "eula_de.txt"; InfoBeforeFile: "info_de.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "eula_en.txt"; InfoBeforeFile: "info_en.txt"

[CustomMessages]
german.DeleteUserData=Sollen auch die heruntergeladenen Modelle, die Engine und die Einstellungen geloescht werden (kann mehrere GB freigeben)?
english.DeleteUserData=Also delete the downloaded models, the engine and the settings (can free several GB)?
german.FirstRun=Yume LLM Server starten und die Engine (llama.cpp) automatisch einrichten
english.FirstRun=Start Yume LLM Server and set up the engine (llama.cpp) automatically
german.FirewallRule=Windows-Firewall: Ports 8080-8082 fuer das Heimnetz freigeben
english.FirewallRule=Windows firewall: allow ports 8080-8081 for the home network

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "firewall"; Description: "{cm:FirewallRule}"; GroupDescription: "{cm:AdditionalIcons}"; Check: IsAdminInstallMode

[Files]
Source: "..\build\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Comment: "{#AppName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Yume LLM Server"""; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Yume LLM Server"" dir=in action=allow protocol=TCP localport=8080-8082 profile=private,domain"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#AppExe}"; Parameters: "--setup"; Description: "{cm:FirstRun}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Yume LLM Server"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"; Check: IsAdminInstallMode

[Code]
procedure StopRunningServer();
var
  exe: String;
  rc: Integer;
begin
  exe := ExpandConstant('{app}\{#AppExe}');
  if FileExists(exe) then
    Exec(exe, '--exit', '', SW_HIDE, ewWaitUntilTerminated, rc);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningServer();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopRunningServer();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'YumeLLMServer');
    if not UninstallSilent then
      if MsgBox(CustomMessage('DeleteUserData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{localappdata}\YumeLLMServer'), True, True, True);
  end;
end;

