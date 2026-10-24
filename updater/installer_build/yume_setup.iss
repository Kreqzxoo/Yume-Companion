; Yume Companion - Windows installer (Inno Setup 6)
; Build:  installer_build\build.bat   (needs Inno Setup 6, see README_DE.md)
;
; The installer copies the cleaned program folder, creates Start-menu / desktop shortcuts, lets the user choose
; the PyTorch variant (CUDA / CPU) and FlashAttention in the wizard, then runs installer.bat unattended
; (downloads the large Python packages). The shortcuts start the program through a small launcher
; (no console window, splash screen with progress). Models are not included.
;
; Command line (for tests / unattended use):  /INSTALLDEPS=0|1  /TORCH=cuda|cpu  /FLASH=0|1

#define AppName      "Yume Companion"
#ifndef AppVersion
  #define AppVersion "2.5.3"
#endif
#define VerNum       Copy(AppVersion, 1, Pos("-", AppVersion + "-") - 1)
#ifndef UpdateOnly
  #define UpdateOnly 0
#endif
#define AppPublisher "Kreqzxoo"
#ifndef SourceDir
  #define SourceDir "C:\Pfad\zu\Yume Companion"
#endif
#ifndef OutDir
  #define OutDir "C:\Pfad\zu\Ausgabe"
#endif
#if UpdateOnly
  #define UpdateExcludes "app\data\*,app\ffmpeg\*,app\utils\ai_clients\backend\*,app\utils\emotions\detector\*,app\utils\e5-small-en-ru\*,"
#else
  #define UpdateExcludes ""
#endif
#define AppIcon      "{app}\assets\custom_branding\yume_app.ico"
#define AumId        "com.sow.custom.Yume_Companion"

[Setup]
#ifdef TestMode
; verification build: own AppId, no uninstaller / registry entry, no compression -> cannot touch a real installation
AppId={{7D1E4C0A-3B52-4F7E-9C6D-2A84B1E5F9FF}
Uninstallable=no
CreateUninstallRegKey=no
#else
AppId={{7D1E4C0A-3B52-4F7E-9C6D-2A84B1E5F903}
#endif
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
; numeric part only (beta suffixes such as 2.5.4-beta1 are not valid here)
VersionInfoVersion={#VerNum}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup

; per-user by default (no admin prompt); the user may switch to an all-users install in the first dialog
PrivilegesRequired=lowest
AppCopyright=Copyright (C) 2026 Kreqzxoo
PrivilegesRequiredOverridesAllowed=dialog commandline
DefaultDirName={autopf}\{#AppName}
UsePreviousAppDir=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
DisableWelcomePage=no

OutputDir={#OutDir}
#if UpdateOnly
OutputBaseFilename=Yume-Companion-Update-{#AppVersion}
#else
OutputBaseFilename=Yume-Companion-Setup-{#AppVersion}
#endif
SetupIconFile=setup_icon.ico
UninstallDisplayIcon={#AppIcon}
UninstallDisplayName={#AppName}
WizardStyle=modern
#ifdef WizardDir
WizardImageFile={#WizardDir}\wizard_large.bmp,{#WizardDir}\wizard_large_2x.bmp
WizardSmallImageFile={#WizardDir}\wizard_small.bmp,{#WizardDir}\wizard_small_2x.bmp
#else
WizardImageFile=wizard_large.bmp,wizard_large_2x.bmp
WizardSmallImageFile=wizard_small.bmp,wizard_small_2x.bmp
#endif

#ifdef TestMode
Compression=none
SolidCompression=no
#else
Compression=lzma2/fast
SolidCompression=yes
LZMANumBlockThreads=4
#endif
DiskSpanning=no

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; program (~4.5 GB, counted from the files) plus the packages installer.bat downloads afterwards (~8-11 GB): about 15.5 GB without AI models
ExtraDiskSpaceRequired=12000000000
SetupLogging=yes
ShowLanguageDialog=auto
CloseApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; LicenseFile: "license_de.txt"; InfoBeforeFile: "info_de.txt"; InfoAfterFile: "infoafter_de.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "license_en.txt"; InfoBeforeFile: "info_en.txt"; InfoAfterFile: "infoafter_en.txt"

[Messages]
german.WizardLicense=Lizenz und rechtliche Hinweise
german.LicenseLabel=Bitte lies die folgenden Lizenz- und Rechtshinweise, bevor du fortfährst.
german.LicenseLabel3=Yume Companion ist freie Software (GPL-3.0). Die Lizenz gibt dir die Rechte zur Nutzung, Änderung und Weitergabe und legt dir keine zusätzlichen Bedingungen auf. Bitte bestätige, dass du die Hinweise gelesen hast.
german.LicenseAccepted=Ich habe die Lizenz- und Rechtshinweise &gelesen
german.LicenseNotAccepted=Ich möchte &nicht fortfahren
english.WizardLicense=Licence and legal notices
english.LicenseLabel=Please read the following licence and legal notices before continuing.
english.LicenseLabel3=Yume Companion is free software (GPL-3.0). The licence gives you the rights to use, modify and share it and imposes no additional conditions on you. Please confirm that you have read the notices.
english.LicenseAccepted=I have &read the licence and legal notices
english.LicenseNotAccepted=I do &not want to continue

[CustomMessages]
german.RepairShortcut=Komponenten installieren oder reparieren
english.RepairShortcut=Install or repair components
german.NoProgramFiles=Ohne Administratorrechte kann nicht in einen geschützten Ordner wie "Programme" installiert werden. Bitte einen anderen Ordner wählen (zum Beispiel den vorgeschlagenen) oder das Setup als Administrator starten.
english.NoProgramFiles=Without administrator rights the program cannot be installed into a protected folder such as "Program Files". Please choose another folder (for example the suggested one) or run the setup as administrator.
german.OneDriveWarn=Der gewählte Ordner liegt in OneDrive. Das Programm ist mehrere Gigabyte groß und schreibt ständig Daten (Chats, Modelle, Logs); OneDrive würde alles synchronisieren und kann Dateien sperren.%n%nTrotzdem diesen Ordner verwenden?
english.OneDriveWarn=The chosen folder is inside OneDrive. The program is several gigabytes in size and writes data constantly (chats, models, logs); OneDrive would sync everything and may lock files.%n%nUse this folder anyway?
german.PathTooLong=Der gewählte Ordnerpfad ist sehr lang. Windows begrenzt Pfadlängen; tief verschachtelte Programmdateien können dann nicht geladen werden und das Programm startet eventuell nicht.%n%nEmpfohlen: ein kurzer Pfad wie C:\Yume oder %USERPROFILE%\Yume.%n%nTrotzdem diesen Ordner verwenden?
english.PathTooLong=The chosen folder path is very long. Windows limits path lengths; deeply nested program files may then fail to load and the program may not start.%n%nRecommended: a short path such as C:\Yume or %USERPROFILE%\Yume.%n%nUse this folder anyway?
german.UninstallDeleteData=Sollen auch alle persönlichen Daten gelöscht werden (Charaktere, Chats, Einstellungen, heruntergeladene Modelle)?%n%nNein = Daten bleiben im Programmordner erhalten.
english.UninstallDeleteData=Also delete all personal data (characters, chats, settings, downloaded models)?%n%nNo = the data stays in the program folder.

german.CompTitle=Komponenten
english.CompTitle=Components
german.CompSubtitle=Wähle, welche Programmteile aus dem Internet installiert werden
english.CompSubtitle=Choose which program parts are downloaded and installed
german.CompIntro=Das Setup lädt jetzt die Python-Pakete für die KI-Funktionen (ca. 8 bis 11 GB, 10 bis 40 Minuten). Wähle die Variante, die zu deinem Computer passt:
german.CompSystem=Dein Computer: %1  |  Arbeitsspeicher: %2 GB  |  Frei auf %3 %4 GB
german.CompSystemUnknown=Die Hardware deines Computers konnte nicht ausgelesen werden.
german.NoGpuFound=keine Grafikkarte erkannt
german.CompCuda=CUDA - für NVIDIA-Grafikkarten (empfohlen)
german.CompCudaNote=Viel schneller bei Sprachausgabe, Bildern und lokalen KI-Modellen. Für GeForce GTX 16xx / RTX, ab 6 GB Grafikspeicher empfohlen. Größerer Download.
german.CompCpu=CPU - ohne NVIDIA-Grafikkarte
german.CompCpuNote=Läuft auf jedem PC, die KI-Funktionen sind aber deutlich langsamer. Auch richtig bei AMD- oder Intel-Grafik: PyTorch nutzt diese Karten unter Windows nicht, Sprachmodelle können im Programm aber trotzdem die Grafikkarte über Vulkan nutzen.
german.CompFlash=FlashAttention-2 mitinstallieren (nur CUDA, schnellere Qwen-Sprachausgabe, ca. 250 MB)
german.CompInstallNow=Komponenten direkt nach dem Kopieren installieren (empfohlen)
german.TaskAutostart=Yume Companion mit Windows starten
german.TaskGroupMore=Weitere Optionen:
german.LowSpace=Auf dem gewählten Laufwerk sind nur %1 GB frei. Das Programm braucht ca. 15,5 GB (ohne KI-Modelle), mit Modellen eher 40 GB.%n%nTrotzdem fortfahren?
german.ReadySize=Speicherbedarf: ca. 15,5 GB (ohne KI-Modelle)
english.CompIntro=The setup now downloads the Python packages for the AI features (about 8 to 11 GB, 10 to 40 minutes). Choose the variant that fits your computer:
english.CompSystem=Your computer: %1  |  Memory: %2 GB  |  Free on %3 %4 GB
english.CompSystemUnknown=The hardware of your computer could not be read.
english.NoGpuFound=no graphics card detected
english.CompCuda=CUDA - for NVIDIA graphics cards (recommended)
english.CompCudaNote=Much faster for speech output, images and local AI models. For GeForce GTX 16xx / RTX, 6 GB or more video memory recommended. Larger download.
english.CompCpu=CPU - without an NVIDIA graphics card
english.CompCpuNote=Runs on any PC, but the AI features are considerably slower. Also the right choice for AMD or Intel graphics: PyTorch does not use those cards on Windows, but language models in the program can still use the graphics card through Vulkan.
english.CompFlash=Also install FlashAttention-2 (CUDA only, faster Qwen speech output, about 250 MB)
english.CompInstallNow=Install the components right after copying (recommended)
english.TaskAutostart=Start Yume Companion with Windows
english.TaskGroupMore=More options:
english.LowSpace=Only %1 GB are free on the chosen drive. The program needs about 15.5 GB (without AI models), about 40 GB with models.%n%nContinue anyway?
english.ReadySize=Disk space: about 15.5 GB (without AI models)
german.StatusComponents=Komponenten werden installiert - das dauert je nach Internetverbindung 10 bis 40 Minuten ...
german.StatusComponentsStep=Komponenten werden installiert - Schritt %1 von %2 (seit %3 Min., bitte nicht schliessen) ...
german.StatusComponentsStart=Komponenten werden vorbereitet (seit %1 Min.) ...
german.DlLine=Lade %1 ... %2 %% (%3 von %4)
german.DlStart=Lade %1 ...
german.DlInstalling=Pakete werden eingerichtet ...
german.CompsLastError=Letzte Fehlermeldungen:
german.StatusExtraPackages=Neue Programmpakete werden installiert ...
english.StatusComponents=Installing components - depending on your connection this takes 10 to 40 minutes ...
english.StatusComponentsStep=Installing components - step %1 of %2 (%3 min so far, please do not close) ...
english.StatusComponentsStart=Preparing components (%1 min so far) ...
english.DlLine=Downloading %1 ... %2 %% (%3 of %4)
english.DlStart=Downloading %1 ...
english.DlInstalling=Setting up packages ...
english.CompsLastError=Last error messages:
english.StatusExtraPackages=Installing new program packages ...
german.CompsFailed=Nicht alle Komponenten konnten installiert werden. Die vollständige Ausgabe steht in logs\installer_console.log (Kurzprotokoll: logs\installer.log). Häufige Ursachen: Internet-Unterbrechung, Firewall/DNS-Filter oder Virenscanner.%n%nDu kannst die Installation später über das Startmenü ("Komponenten installieren oder reparieren") wiederholen.
english.CompsFailed=Not all components could be installed. The full output is in logs\installer_console.log (short log: logs\installer.log). Common causes: interrupted internet connection, firewall / DNS filter or virus scanner.%n%nYou can repeat the installation later from the Start menu ("Install or repair components").
german.ReadyComponents=Komponenten:
english.ReadyComponents=Components:
german.ReadyTorchCuda=PyTorch mit CUDA
english.ReadyTorchCuda=PyTorch with CUDA
german.ReadyTorchCpu=PyTorch nur CPU
english.ReadyTorchCpu=PyTorch CPU only
german.ReadyFlashYes=FlashAttention-2: ja
english.ReadyFlashYes=FlashAttention-2: yes
german.ReadyFlashNo=FlashAttention-2: nein
english.ReadyFlashNo=FlashAttention-2: no
german.ReadyNoInstall=Nicht jetzt installieren (später über das Startmenü)
english.ReadyNoInstall=Not installing now (later via the Start menu)
german.ConsoleShortcut=mit Konsole - Fehlersuche
english.ConsoleShortcut=with console - troubleshooting

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:TaskGroupMore}"; Flags: unchecked

[Dirs]
; all-users installs: the program writes its data into its own folder, so normal users need write access
Name: "{app}"; Permissions: users-modify; Check: IsAdminInstallMode

[Files]
Source: "setup_icon.ico"; DestDir: "{app}\assets\custom_branding"; DestName: "yume_app.ico"; Flags: ignoreversion
; the program; user data of a running copy of the source folder is never packed
Source: "launcher\Yume Companion.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "{#UpdateExcludes}Yume Companion.exe,app\configuration\settings.json,app\configuration\api.json,app\configuration\characters.json,app\configuration\android_devices.json,.soul\*,.soul_stage\*,backups\*,logs\*.log"; Flags: ignoreversion recursesubdirs createallsubdirs
; fresh default configuration (program language follows the setup language) - never overwritten on updates / repairs
Source: "{#SourceDir}\app\configuration\settings.json"; DestDir: "{app}\app\configuration"; Languages: english; Check: InstallSettings; Flags: uninsneveruninstall
Source: "templates\settings_de.json"; DestDir: "{app}\app\configuration"; DestName: "settings.json"; Languages: german; Check: InstallSettings; Flags: uninsneveruninstall
Source: "{#SourceDir}\app\configuration\api.json"; DestDir: "{app}\app\configuration"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceDir}\app\configuration\characters.json"; DestDir: "{app}\app\configuration"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
; the verification build must not touch shortcuts: they have the same names as the real ones and would replace them
#ifndef TestMode
Name: "{autoprograms}\{#AppName}\{#AppName}"; Filename: "{app}\Yume Companion.exe"; WorkingDir: "{app}"; IconFilename: "{#AppIcon}"; AppUserModelID: "{#AumId}"; Comment: "{#AppName}"
Name: "{autoprograms}\{#AppName}\{#AppName} ({cm:ConsoleShortcut})"; Filename: "{app}\start.bat"; WorkingDir: "{app}"; IconFilename: "{#AppIcon}"
Name: "{autoprograms}\{#AppName}\{cm:RepairShortcut}"; Filename: "{app}\installer.bat"; WorkingDir: "{app}"; IconFilename: "{#AppIcon}"
Name: "{autoprograms}\{#AppName}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Yume Companion.exe"; WorkingDir: "{app}"; IconFilename: "{#AppIcon}"; AppUserModelID: "{#AumId}"; Comment: "{#AppName}"; Tasks: desktopicon
#endif

[Registry]
#ifndef TestMode
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\Yume Companion.exe"""; Flags: uninsdeletevalue; Tasks: autostart
#endif

[Run]
Filename: "{app}\Yume Companion.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
var
  CompPage: TWizardPage;
  LblIntro, LblSystem, LblCudaNote, LblCpuNote: TNewStaticText;
  RbCuda, RbCpu: TNewRadioButton;
  CbFlash, CbInstall: TNewCheckBox;

function InstallSettings: Boolean;
var
  F: String;
  S: AnsiString;
begin
  { fresh install, or the unusable text-typed template of earlier builds ("program_language": "0"); real user settings are kept }
  F := ExpandConstant('{app}\app\configuration\settings.json');
  Result := not FileExists(F);
  if (not Result) and LoadStringFromFile(F, S) then
    Result := (Pos('"program_language": "', S) > 0) or (Pos('"input_device": "', S) > 0);
end;

function HasNvidiaGpu: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\nvcuda.dll')) or FileExists(ExpandConstant('{sys}\nvidia-smi.exe'));
end;

function TorchIsCuda: Boolean;
var
  P: String;
begin
  P := Lowercase(ExpandConstant('{param:TORCH|}'));
  if P <> '' then
    Result := (P = 'cuda')
  else
    Result := RbCuda.Checked;
end;

function WantFlash: Boolean;
var
  P: String;
begin
  if not TorchIsCuda then
  begin
    Result := False;
    Exit;
  end;
  P := ExpandConstant('{param:FLASH|}');
  if P <> '' then
    Result := (P = '1')
  else
    Result := CbFlash.Checked;
end;

function WantInstallDeps: Boolean;
var
  P: String;
begin
  P := ExpandConstant('{param:INSTALLDEPS|}');
  if {#UpdateOnly} = 1 then
    Result := False
  else if P <> '' then
    Result := (P = '1')
  else if WizardSilent then
    Result := False
  else
    Result := CbInstall.Checked;
end;

procedure UpdateComponentControls(Sender: TObject);
begin
  CbFlash.Enabled := RbCuda.Checked and CbInstall.Checked;
  RbCuda.Enabled := CbInstall.Checked;
  RbCpu.Enabled := CbInstall.Checked;
end;

function WmiList(Query, Prop: String): String;
var
  Locator, Service, Rows, Row: Variant;
  Value: String;
  I: Integer;
begin
  Result := '';
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Rows := Service.ExecQuery(Query);
    for I := 0 to Rows.Count - 1 do
    begin
      Row := Rows.ItemIndex(I);
      if Result <> '' then
        Result := Result + ', ';
      Value := Row.Properties_.Item(Prop).Value;
      Result := Result + Value;
    end;
  except
  end;
end;

function FreeGbOf(Path: String): Integer;
var
  Free, Total: Int64;
begin
  Result := -1;
  if GetSpaceOnDisk64(ExtractFileDrive(Path) + '\', Free, Total) then
    Result := Integer(Free div 1073741824);
end;

procedure RefreshSystemInfo;
var
  Gpu: String;
  Total: Int64;
  RamGb: Integer;
begin
  Gpu := WmiList('SELECT Name FROM Win32_VideoController', 'Name');
  Total := StrToInt64Def(WmiList('SELECT TotalPhysicalMemory FROM Win32_ComputerSystem', 'TotalPhysicalMemory'), 0);
  RamGb := Integer((Total + 536870912) div 1073741824);
  if (Gpu = '') and (RamGb = 0) then
    LblSystem.Caption := CustomMessage('CompSystemUnknown')
  else
  begin
    if Gpu = '' then
      Gpu := CustomMessage('NoGpuFound');
    LblSystem.Caption := FmtMessage(CustomMessage('CompSystem'), [Gpu, IntToStr(RamGb), ExtractFileDrive(WizardDirValue), IntToStr(FreeGbOf(WizardDirValue))]);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CompPage <> nil) and (CurPageID = CompPage.ID) then
    RefreshSystemInfo;
end;

function AddLabel(Top, Height, Left: Integer; Text: String; Small: Boolean): TNewStaticText;
begin
  Result := TNewStaticText.Create(CompPage);
  Result.Parent := CompPage.Surface;
  Result.AutoSize := False;
  Result.WordWrap := True;
  Result.Left := ScaleX(Left);
  Result.Top := ScaleY(Top);
  Result.Width := CompPage.SurfaceWidth - ScaleX(Left);
  Result.Height := ScaleY(Height);
  Result.Caption := Text;
  if Small then
  begin
    Result.Font.Size := 8;
    Result.Font.Color := $707070;
  end;
end;

procedure InitializeWizard;
begin
  CompPage := CreateCustomPage(wpSelectTasks, CustomMessage('CompTitle'), CustomMessage('CompSubtitle'));

  LblIntro := AddLabel(0, 30, 0, CustomMessage('CompIntro'), False);
  LblSystem := AddLabel(34, 28, 0, '', True);

  RbCuda := TNewRadioButton.Create(CompPage);
  RbCuda.Parent := CompPage.Surface;
  RbCuda.Left := ScaleX(8);
  RbCuda.Top := ScaleY(66);
  RbCuda.Width := CompPage.SurfaceWidth - ScaleX(16);
  RbCuda.Height := ScaleY(18);
  RbCuda.Caption := CustomMessage('CompCuda');
  RbCuda.Checked := HasNvidiaGpu;
  RbCuda.OnClick := @UpdateComponentControls;
  LblCudaNote := AddLabel(84, 28, 26, CustomMessage('CompCudaNote'), True);

  RbCpu := TNewRadioButton.Create(CompPage);
  RbCpu.Parent := CompPage.Surface;
  RbCpu.Left := ScaleX(8);
  RbCpu.Top := ScaleY(116);
  RbCpu.Width := CompPage.SurfaceWidth - ScaleX(16);
  RbCpu.Height := ScaleY(18);
  RbCpu.Caption := CustomMessage('CompCpu');
  RbCpu.Checked := not HasNvidiaGpu;
  RbCpu.OnClick := @UpdateComponentControls;
  LblCpuNote := AddLabel(134, 40, 26, CustomMessage('CompCpuNote'), True);

  CbFlash := TNewCheckBox.Create(CompPage);
  CbFlash.Parent := CompPage.Surface;
  CbFlash.Left := ScaleX(8);
  CbFlash.Top := ScaleY(180);
  CbFlash.Width := CompPage.SurfaceWidth - ScaleX(16);
  CbFlash.Height := ScaleY(18);
  CbFlash.Caption := CustomMessage('CompFlash');
  CbFlash.Checked := True;

  CbInstall := TNewCheckBox.Create(CompPage);
  CbInstall.Parent := CompPage.Surface;
  CbInstall.Left := ScaleX(8);
  CbInstall.Top := ScaleY(204);
  CbInstall.Width := CompPage.SurfaceWidth - ScaleX(16);
  CbInstall.Height := ScaleY(18);
  CbInstall.Caption := CustomMessage('CompInstallNow');
  CbInstall.Checked := True;
  CbInstall.OnClick := @UpdateComponentControls;

  UpdateComponentControls(nil);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ({#UpdateOnly} = 1) and (PageID = CompPage.ID);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir: String;
  FreeGb: Integer;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Dir := Lowercase(WizardDirValue);
    if (not IsAdminInstallMode) and
       ((Pos(Lowercase(ExpandConstant('{commonpf64}')), Dir) = 1) or (Pos(Lowercase(ExpandConstant('{commonpf32}')), Dir) = 1)) then
    begin
      MsgBox(CustomMessage('NoProgramFiles'), mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Pos('\onedrive', Dir) > 0 then
      Result := MsgBox(CustomMessage('OneDriveWarn'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    if Result and (Length(Dir) > 80) then
      Result := MsgBox(CustomMessage('PathTooLong'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    if Result and ({#UpdateOnly} = 0) then
    begin
      FreeGb := FreeGbOf(WizardDirValue);
      if (FreeGb >= 0) and (FreeGb < 16) then
        Result := MsgBox(FmtMessage(CustomMessage('LowSpace'), [IntToStr(FreeGb)]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    end;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  S: String;
begin
  S := MemoDirInfo;
  if MemoTasksInfo <> '' then
    S := S + NewLine + NewLine + MemoTasksInfo;
  S := S + NewLine + NewLine + CustomMessage('ReadyComponents') + NewLine;
  if WantInstallDeps then
  begin
    if TorchIsCuda then
      S := S + Space + CustomMessage('ReadyTorchCuda') + NewLine
    else
      S := S + Space + CustomMessage('ReadyTorchCpu') + NewLine;
    if WantFlash then
      S := S + Space + CustomMessage('ReadyFlashYes') + NewLine
    else
      S := S + Space + CustomMessage('ReadyFlashNo') + NewLine;
  end
  else
    S := S + Space + CustomMessage('ReadyNoInstall') + NewLine;
  if {#UpdateOnly} = 0 then
    S := S + NewLine + CustomMessage('ReadySize') + NewLine;
  Result := S;
end;

function HasExtraPackages(FileName: String): Boolean;
var
  Lines: TArrayOfString;
  I: Integer;
  S: String;
begin
  Result := False;
  if LoadStringsFromFile(FileName, Lines) then
    for I := 0 to GetArrayLength(Lines) - 1 do
    begin
      S := Trim(Lines[I]);
      if (S <> '') and (Copy(S, 1, 1) <> '#') then
      begin
        Result := True;
        Exit;
      end;
    end;
end;

{ keeps the wizard alive (repaint, move, no "not responding") while the script waits - the usual Windows message pump }
type
  TPeekPoint = record
    X: Longint;
    Y: Longint;
  end;
  TPeekMsg = record
    Wnd: Longword;
    Msg: Longword;
    WParam: Longword;
    LParam: Longint;
    Time: Longword;
    Pt: TPeekPoint;
  end;

function PeekMessageW(var Msg: TPeekMsg; Wnd: Longword; FilterMin, FilterMax, Remove: Longword): Longint; external 'PeekMessageW@user32.dll stdcall';
function TranslateMessage(var Msg: TPeekMsg): Longint; external 'TranslateMessage@user32.dll stdcall';
function DispatchMessageW(var Msg: TPeekMsg): Longint; external 'DispatchMessageW@user32.dll stdcall';

procedure AppProcessMessage;
var
  Msg: TPeekMsg;
begin
  while PeekMessageW(Msg, 0, 0, 0, 1) <> 0 do
  begin
    TranslateMessage(Msg);
    DispatchMessageW(Msg);
  end;
end;

function SizeText(N: Int64): String;
begin
  if N >= 1073741824 then
    Result := IntToStr(N div 1073741824) + ',' + IntToStr(((N mod 1073741824) * 10) div 1073741824) + ' GB'
  else
    Result := IntToStr(N div 1048576) + ' MB';
end;

{ the last "Progress 123 of 456" line of pip (pip is started with PIP_PROGRESS_BAR=raw, which prints such lines even into a log file) }
function LastProgress(const S: String; var Cur, Total: Int64): Boolean;
var
  I, J: Integer;
  A, B: String;
begin
  Result := False;
  for I := Length(S) - 12 downto 1 do
    if (S[I] = 'P') and (Copy(S, I, 9) = 'Progress ') then
    begin
      J := I + 9;
      A := '';
      while (J <= Length(S)) and (S[J] >= '0') and (S[J] <= '9') do
      begin
        A := A + S[J];
        J := J + 1;
      end;
      if Copy(S, J, 4) = ' of ' then
      begin
        J := J + 4;
        B := '';
        while (J <= Length(S)) and (S[J] >= '0') and (S[J] <= '9') do
        begin
          B := B + S[J];
          J := J + 1;
        end;
        Cur := StrToInt64Def(A, 0);
        Total := StrToInt64Def(B, 0);
        Result := Total > 0;
        Exit;
      end;
    end;
end;

{ name of the file pip downloads right now ("Downloading torch-2.10.0+cu128-... (2.4 GB)" at the start of a line) and the position of that line }
function LastDownloadName(const S: String; var LinePos: Integer): String;
var
  I, J: Integer;
begin
  Result := '';
  LinePos := 0;
  for I := Length(S) - 12 downto 1 do
    if (S[I] = #10) and (Copy(S, I + 1, 12) = 'Downloading ') then
    begin
      J := I + 13;
      while (J <= Length(S)) and (S[J] <> ' ') and (S[J] <> #13) and (S[J] <> #10) do
        J := J + 1;
      Result := Copy(S, I + 13, J - I - 13);
      LinePos := I;
      if Length(Result) > 48 then
        Result := Copy(Result, 1, 48) + '...';
      Exit;
    end;
end;

{ waits until the hidden installer.bat has written its marker file; meanwhile shows the step (n of 8), the download progress of the file that
  is loaded right now (percent, MB) and how long it has been running }
procedure WaitForInstaller(LogFile, Marker: String);
var
  Raw: AnsiString;
  Text, Line, Name, Elapsed: String;
  Step, I, P, Ticks, Secs, LinePos, Pos1000, Base, Frac, CopyCode: Integer;
  Cur, Total: Int64;
  Pct: Integer;
  Installing: Boolean;
begin
  Ticks := 0;
  while (not FileExists(Marker)) and (Ticks < 20000) do
  begin
    Sleep(700);
    Ticks := Ticks + 1;
    Secs := (Ticks * 7) div 10;
    Elapsed := IntToStr(Secs div 60) + ':' + Copy('0' + IntToStr(Secs mod 60), Length('0' + IntToStr(Secs mod 60)) - 1, 2);
    Exec(ExpandConstant('{cmd}'), '/C copy /Y "' + LogFile + '" "' + LogFile + '.snap" >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, CopyCode);
    if LoadStringFromFile(LogFile + '.snap', Raw) then
    begin
      Text := String(Raw);
      Step := 0;
      for I := 8 downto 1 do
        if Pos('[' + IntToStr(I) + '/8]', Text) > 0 then
        begin
          Step := I;
          Break;
        end;
      Frac := 0;
      Line := '';
      Name := LastDownloadName(Text, LinePos);
      Installing := (LinePos > 0) and (Pos('Installing collected packages', Copy(Text, LinePos, Length(Text))) > 0);
      if (Name <> '') and (not Installing) and LastProgress(Text, Cur, Total) and (LinePos > 0) and (Pos('Progress ', Copy(Text, LinePos, Length(Text))) > 0) then
      begin
        Pct := Integer((Cur * 100) div Total);
        Frac := Pct * 10;
        Line := FmtMessage(CustomMessage('DlLine'), [Name, IntToStr(Pct), SizeText(Cur), SizeText(Total)]);
      end
      else if Installing then
        Line := CustomMessage('DlInstalling')
      else if Name <> '' then
        Line := FmtMessage(CustomMessage('DlStart'), [Name]);
      if Step > 0 then
      begin
        Base := (Step - 1) * 125;
        Pos1000 := Base + (Frac * 125) div 1000;
        if Pos1000 > WizardForm.ProgressGauge.Position then
          WizardForm.ProgressGauge.Position := Pos1000;
        WizardForm.StatusLabel.Caption := FmtMessage(CustomMessage('StatusComponentsStep'), [IntToStr(Step), '8', Elapsed]);
      end
      else
        WizardForm.StatusLabel.Caption := FmtMessage(CustomMessage('StatusComponentsStart'), [Elapsed]);
      if Line = '' then
      begin
        { nothing to report from pip yet: the last line of the log }
        P := Length(Text);
        while (P > 0) and ((Text[P] = #10) or (Text[P] = #13) or (Text[P] = ' ')) do
          P := P - 1;
        I := P;
        while (I > 0) and (Text[I] <> #10) and (Text[I] <> #13) do
          I := I - 1;
        Line := Copy(Text, I + 1, P - I);
        if Length(Line) > 90 then
          Line := Copy(Line, 1, 90) + '...';
      end;
      WizardForm.FilenameLabel.Caption := Line;
    end
    else
      WizardForm.StatusLabel.Caption := FmtMessage(CustomMessage('StatusComponentsStart'), [Elapsed]);
    AppProcessMessage;
  end;
end;

{ the last few error lines of the installer output, shown in the message when the components could not be installed }
function LastErrorLines(LogFile: String): String;
var
  Lines: TArrayOfString;
  I, N: Integer;
  S: String;
begin
  Result := '';
  if not LoadStringsFromFile(LogFile, Lines) then
    Exit;
  N := 0;
  for I := GetArrayLength(Lines) - 1 downto 0 do
  begin
    S := Trim(Lines[I]);
    if (Pos('ERROR', S) > 0) or (Pos('failed', S) > 0) or (Pos('Could not', S) > 0) or (Pos('could not be', S) > 0) then
    begin
      if Length(S) > 150 then
        S := Copy(S, 1, 150) + '...';
      Result := S + #13#10 + Result;
      N := N + 1;
      if N >= 3 then
        Break;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, Args, ConsoleLog, DoneMarker, FailText, FailLines: String;
  DoneText: AnsiString;
  ResultCode: Integer;
  ComponentsOk: Boolean;
begin
  if (CurStep = ssPostInstall) and WantInstallDeps then
  begin
    AppDir := ExpandConstant('{app}');
    if TorchIsCuda then
      Args := '/auto cuda'
    else
      Args := '/auto cpu';
    if WantFlash then
      Args := Args + ' flash';
    WizardForm.StatusLabel.Caption := CustomMessage('StatusComponents');
    WizardForm.FilenameLabel.Caption := '';
    { no console window: installer.bat runs hidden, its output goes to a log file and the wizard shows the steps and the last line }
    ForceDirectories(AppDir + '\logs');
    ConsoleLog := AppDir + '\logs\installer_console.log';
    DoneMarker := AppDir + '\logs\installer_done.txt';
    DeleteFile(ConsoleLog);
    DeleteFile(DoneMarker);
    WizardForm.ProgressGauge.Min := 0;
    WizardForm.ProgressGauge.Max := 1000;
    WizardForm.ProgressGauge.Position := 0;
    ComponentsOk := False;
    if Exec(ExpandConstant('{cmd}'), '/V:ON /C "set PIP_PROGRESS_BAR=raw& "' + AppDir + '\installer.bat" ' + Args + ' < nul > "' + ConsoleLog + '" 2>&1 & echo !errorlevel! > "' + DoneMarker + '""', AppDir, SW_HIDE, ewNoWait, ResultCode) then
    begin
      WaitForInstaller(ConsoleLog, DoneMarker);
      if LoadStringFromFile(DoneMarker, DoneText) then
        ComponentsOk := Trim(String(DoneText)) = '0';
    end;
    if not ComponentsOk then
    begin
      FailText := CustomMessage('CompsFailed');
      FailLines := LastErrorLines(ConsoleLog);
      if FailLines <> '' then
        FailText := FailText + #13#10#13#10 + CustomMessage('CompsLastError') + #13#10 + FailLines;
      SuppressibleMsgBox(FailText, mbError, MB_OK, IDOK);
    end;
  end;

  { updates: install packages that were added after the last full install (list in requirements_extra.txt) }
  if (CurStep = ssPostInstall) and (not WantInstallDeps) then
  begin
    AppDir := ExpandConstant('{app}');
    if FileExists(AppDir + '\requirements_extra.txt') and HasExtraPackages(AppDir + '\requirements_extra.txt') and FileExists(AppDir + '\app\data\envs\sow\python.exe') then
    begin
      WizardForm.StatusLabel.Caption := CustomMessage('StatusExtraPackages');
      WizardForm.FilenameLabel.Caption := '';
      Exec(ExpandConstant('{cmd}'), '/C ""' + AppDir + '\app\data\envs\sow\python.exe" -m pip install --no-cache-dir -r "' + AppDir + '\requirements_extra.txt" > "' + AppDir + '\logs\update_packages.log" 2>&1"', AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    { packages that installer.bat downloaded (several GB) are not part of the install manifest }
    DelTree(AppDir + '\app\data\envs', True, True, True);
    if (not UninstallSilent) and
       (MsgBox(CustomMessage('UninstallDeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(AppDir, True, True, True);
  end;
end;
