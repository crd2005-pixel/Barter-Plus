[Setup]
AppName=Barter Plus Unificador de Listas
AppVersion=2.0
DefaultDirName={autopf}\BarterPlusUnificador
DisableProgramGroupPage=yes
OutputBaseFilename=Instalador_Unificador

[Files]
; Falla 8: Volcar contenido manteniendo subcarpetas internas correctas
Source: "dist\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Prohibido sobreescribir DBs (aunque en unificador_listas no hay local DB de producción, es buena práctica)
Excludes: "*.db,*.sqlite,*.sqlite3"

[Icons]
Name: "{autoprograms}\Barter Plus Unificador"; Filename: "{app}\app.exe"; IconFilename: "{app}\ICONO.ico"
Name: "{autodesktop}\Barter Plus Unificador"; Filename: "{app}\app.exe"; IconFilename: "{app}\ICONO.ico"
