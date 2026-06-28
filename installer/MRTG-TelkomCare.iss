#define MyAppName "MRTG TelkomCare Report Automation"
#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "mriazh"
#define MyAppURL "https://github.com/mriazh/MRTG-TelkomCare-Report-Automation"
#define MyAppExeName "MRTG-TelkomCare.exe"

[Setup]
AppId={{9F5F89AD-8B0C-4A73-BCA4-D3C5C7A9E1E4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\MRTG TelkomCare
DefaultGroupName=MRTG TelkomCare
OutputDir=..\release
OutputBaseFilename=MRTG-TelkomCare-Setup-v{#MyAppVersion}
SetupIconFile=..\assets\app_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\MRTG-TelkomCare\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
