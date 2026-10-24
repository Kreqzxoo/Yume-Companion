; Yume Release Tool - installer (Inno Setup 6)
; Build with "Build Updater Installer.ps1" (compiles the launcher exe first).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Yume Release Tool"
#define OutDir  "..\Yume Updater Setup"

[Setup]
AppId={{3B6E2D91-5A4C-4E0F-8D77-1C9A5B7E42A6}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Kreqzxoo
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DefaultDirName={autopf}\Yume Updater
UsePreviousAppDir=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#OutDir}
OutputBaseFilename=Yume-Updater-Setup-{#AppVersion}
SetupIconFile=installer_build\setup_icon.ico
UninstallDisplayIcon={app}\Yume Updater.exe
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=installer_build\wizard_large.bmp,installer_build\wizard_large_2x.bmp
WizardSmallImageFile=installer_build\wizard_small.bmp,installer_build\wizard_small_2x.bmp
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; InfoBeforeFile: "info_updater_de.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "info_updater_en.txt"

[CustomMessages]
german.DeleteUserData=Sollen auch die gespeicherten Einstellungen und Protokolle des Tools geloescht werden?
english.DeleteUserData=Also delete the tool's saved settings and logs?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "Yume Updater.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Yume Release Tool.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Yume Build.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Yume Verify.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Yume Doctor.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "YumeUpdaterLauncher.cs"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer_build\*"; DestDir: "{app}\installer_build"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Yume Updater.exe"; WorkingDir: "{app}"; Comment: "{#AppName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Yume Updater.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Yume Updater.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\installer_build\launcher\Yume Companion.exe.bak"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(CustomMessage('DeleteUserData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\Yume Updater'), True, True, True);
end;
