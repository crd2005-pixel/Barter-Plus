[Setup]
AppName=Unificador de Listas
AppVersion=1.0
AppPublisher=Barter Plus
DefaultDirName={pf}\Unificador de Listas
DefaultGroupName=Unificador de Listas
OutputDir=.\Output
OutputBaseFilename=Instalador_Unificador
SetupIconFile=icono_unificador.ico
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\Unificador de Listas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Unificador de Listas"; Filename: "{app}\Unificador de Listas.exe"; IconFilename: "{app}\icono_unificador.ico"
Name: "{commondesktop}\Unificador de Listas"; Filename: "{app}\Unificador de Listas.exe"; IconFilename: "{app}\icono_unificador.ico"

[Run]
Filename: "{app}\Unificador de Listas.exe"; Description: "Ejecutar Unificador de Listas"; Flags: nowait postinstall skipifsilent
