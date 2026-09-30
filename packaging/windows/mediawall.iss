; Inno Setup script for MediaWall's Windows installer.
; Run by packaging/build.py, which passes AppVersion, SourceDir (the
; PyInstaller folder), OutputDir, and IconFile with /D.
;
; Installs per user by default (no admin prompt), with an option to
; install for everyone. Settings (the registry) and logs
; (%LOCALAPPDATA%\MediaWall) are left in place on uninstall.

[Setup]
; Identifies MediaWall to Windows across versions: never change it.
AppId={{826848C3-1FED-4C45-84A7-5E011B3DE82F}
AppName=MediaWall
AppVersion={#AppVersion}
; Shown in Installed apps (appwiz.cpl) and the wizard: "MediaWall 0.9.2",
; not Inno's default "MediaWall version 0.9.2".
AppVerName=MediaWall {#AppVersion}
AppPublisher=evans.tools
DefaultDirName={autopf}\MediaWall
DefaultGroupName=MediaWall
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=MediaWall-{#AppVersion}-Setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\MediaWall.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "Open .mediawall project files with MediaWall"; GroupDescription: "File types:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; An upgrade replaces the whole app folder, so files dropped from a new
; version don't linger.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\MediaWall"; Filename: "{app}\MediaWall.exe"
Name: "{autodesktop}\MediaWall"; Filename: "{app}\MediaWall.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.mediawall"; ValueType: string; ValueName: ""; ValueData: "MediaWall.Project"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\.mediawall\OpenWithProgids"; ValueType: string; ValueName: "MediaWall.Project"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\MediaWall.Project"; ValueType: string; ValueName: ""; ValueData: "MediaWall project"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\MediaWall.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\MediaWall.exe,0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\MediaWall.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\MediaWall.exe"" ""%1"""; Tasks: associate

[Run]
Filename: "{app}\MediaWall.exe"; Description: "{cm:LaunchProgram,MediaWall}"; Flags: nowait postinstall skipifsilent
