[Setup]
AppName=Barter Plus
AppVersion=1.0
AppPublisher=VertexCubic
DefaultDirName={autopf}\Barter Plus
DisableProgramGroupPage=yes
; Usa el logo corporativo para el instalador
SetupIconFile=logo.ico
OutputDir=.\Output
OutputBaseFilename=BarterPlus_Update_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Toma todo el contenido de la carpeta dist compilada
Source: "dist\Barter Plus\*"; DestDir: "{app}"; Excludes: "*.db,*.sqlite,*.sqlite3"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Barter Plus"; Filename: "{app}\Barter Plus.exe"; IconFilename: "{app}\Barter Plus.exe"
Name: "{autodesktop}\Barter Plus"; Filename: "{app}\Barter Plus.exe"; Tasks: desktopicon; IconFilename: "{app}\Barter Plus.exe"

[Run]
Filename: "{app}\Barter Plus.exe"; Description: "{cm:LaunchProgram,Barter Plus}"; Flags: nowait postinstall skipifsilent