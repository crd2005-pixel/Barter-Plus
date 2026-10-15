[Setup]
AppName=Unificador Barter Plus
AppVersion=1.0
DefaultDirName={pf}\UnificadorBarterPlus
DefaultGroupName=Unificador Barter Plus
OutputBaseFilename=Instalar_Unificador
SetupIconFile=ICONO.ico
Compression=lzma
SolidCompression=yes

[Files]
Source: "app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "lanzador.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "ICONO.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{commondesktop}\Unificador Barter Plus"; Filename: "{app}\lanzador.vbs"; IconFilename: "{app}\ICONO.ico"; WorkingDir: "{app}"
