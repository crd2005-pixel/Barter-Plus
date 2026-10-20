[Setup]
AppName=Unificador de Listas - Barter Plus
AppVersion=1.0
DefaultDirName={autopf}\BarterPlus_Unificador
OutputDir=Instalador_Final
OutputBaseFilename=Setup_Unificador_BarterPlus
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\UnificadorBarterPlus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Unificador de Listas - Barter Plus"; Filename: "{app}\UnificadorBarterPlus.exe"
Name: "{autodesktop}\Unificador de Listas - Barter Plus"; Filename: "{app}\UnificadorBarterPlus.exe"

[Run]
Filename: "{app}\UnificadorBarterPlus.exe"; Description: "Ejecutar Unificador de Listas"; Flags: nowait postinstall skipifsilent