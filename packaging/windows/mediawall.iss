; Inno Setup script for Mediawall's Windows installer.
; Run by packaging/build.py, which passes AppVersion, SourceDir (the
; PyInstaller folder), OutputDir, and IconFile with /D.
;
; Installs per user by default (no admin prompt), with an option to
; install for everyone. Settings (the registry) and logs
; (%LOCALAPPDATA%\Mediawall) are left in place on uninstall.

[Setup]
; Identifies Mediawall to Windows across versions: never change it.
AppId={{826848C3-1FED-4C45-84A7-5E011B3DE82F}
AppName=Mediawall
AppVersion={#AppVersion}
; Shown in Installed apps (appwiz.cpl) and the wizard: "Mediawall 0.9.2",
; not Inno's default "Mediawall version 0.9.2".
AppVerName=Mediawall {#AppVersion}
AppPublisher=evans.tools
DefaultDirName={autopf}\Mediawall
DefaultGroupName=Mediawall
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=Mediawall-{#AppVersion}-Setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\Mediawall.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "Open .mediawall project files with Mediawall"; GroupDescription: "File types:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; An upgrade replaces the whole app folder, so files dropped from a new
; version don't linger.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Mediawall"; Filename: "{app}\Mediawall.exe"
Name: "{autodesktop}\Mediawall"; Filename: "{app}\Mediawall.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.mediawall"; ValueType: string; ValueName: ""; ValueData: "Mediawall.Project"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\.mediawall\OpenWithProgids"; ValueType: string; ValueName: "Mediawall.Project"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\Mediawall.Project"; ValueType: string; ValueName: ""; ValueData: "Mediawall project"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\Mediawall.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Mediawall.exe,0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\Mediawall.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Mediawall.exe"" ""%1"""; Tasks: associate

[Run]
Filename: "{app}\Mediawall.exe"; Description: "{cm:LaunchProgram,Mediawall}"; Flags: nowait postinstall skipifsilent
