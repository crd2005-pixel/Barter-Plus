[Setup]
AppName=Unificador Barter Plus
AppVersion=1.0
DefaultDirName={pf}\BarterPlus\Unificador
DefaultGroupName=Barter Plus
OutputDir=.
OutputBaseFilename=Instalador_Unificador_BarterPlus
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "dist\Unificador_BarterPlus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "api_key.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{commondesktop}\Unificador Barter Plus"; Filename: "{app}\Unificador_BarterPlus.exe"; WorkingDir: "{app}"
Name: "{group}\Unificador Barter Plus"; Filename: "{app}\Unificador_BarterPlus.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Unificador_BarterPlus.exe"; Description: "Ejecutar Unificador Barter Plus"; Flags: nowait postinstall skipifsilent
