; Archivo de configuracion para Inno Setup (http://www.jrsoftware.org/isinfo.php)
; Te permite crear un instalador "Siguiente > Siguiente > Siguiente" para Windows.

[Setup]
AppName=BarterPlus
AppVersion=1.0
AppPublisher=Lubricentro Software
DefaultDirName={pf}\BarterPlus
DefaultGroupName=BarterPlus
OutputDir=.\Instalador
OutputBaseFilename=Instalar_BarterPlus
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Asegurate de haber corrido `compilar.bat` primero para que exista el .exe en `dist\`
Source: "dist\BarterPlus.exe"; DestDir: "{app}"; Flags: ignoreversion
; Si tienes una base de datos SQLite inicial por defecto, puedes incluirla aqui:
; Source: "lubricentro.db"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\BarterPlus"; Filename: "{app}\BarterPlus.exe"
Name: "{commondesktop}\BarterPlus"; Filename: "{app}\BarterPlus.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BarterPlus.exe"; Description: "{cm:LaunchProgram,BarterPlus}"; Flags: nowait postinstall skipifsilent
