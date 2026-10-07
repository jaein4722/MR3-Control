#ifndef AppVersion
  #error Build with packaging/build.ps1 to supply the version from VERSION.
#endif
#define AppExe "MR3 Control.exe"

[Setup]
AppId={{B6A167EC-786E-4D62-B154-9C57ED9728D4}
AppName=MR3 Control
AppVersion={#AppVersion}
AppPublisher=MR3 Control
DefaultDirName={localappdata}\Programs\MR3 Control
DefaultGroupName=MR3 Control
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern
SetupIconFile=..\assets\mr3.ico
UninstallDisplayIcon={app}\{#AppExe}
AppMutex=Local\MR3ControlDesktop
CloseApplications=no
RestartApplications=no
Compression=lzma2
SolidCompression=yes
OutputDir=..\release
OutputBaseFilename=MR3-Control-{#AppVersion}-Setup-x64
VersionInfoVersion={#AppVersion}.0
InfoBeforeFile=install-notes.txt

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\MR3 Control\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MR3 Control"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\MR3 Control"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,MR3 Control}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
begin
  if CurUninstallStep = usUninstall then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'MR3 Control', Command) then
      if CompareText(Command, '"' + ExpandConstant('{app}\{#AppExe}') + '"') = 0 then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'MR3 Control');
  { Keep user settings, backups, and Windows Bluetooth bonds. }
end;
