; ============================================================
;  NMTBot — Instalador (Inno Setup)
;  Gera NMTBot-Setup-vX.Y.Z.exe
;
;  Como compilar:
;    1. Instale Inno Setup (https://jrsoftware.org/isdl.php)
;    2. Abra este arquivo .iss no Inno Setup Compiler
;    3. Compile (Build) -> gera installer\Output\NMTBot-Setup.exe
; ============================================================

#define MyAppName "NMTBot"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "NMTBot"
#define MyAppExeName "main.py"
#define MyAppURL "https://nmt.gg"

[Setup]
AppId={{NMTBOT-2026-001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NMTBot
DefaultGroupName=NMTBot
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=NMTBot-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=..\assets\nmt_bot_icon.ico
UninstallDisplayIcon={app}\assets\nmt_bot_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilian"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
; Arquivos do projeto
Source: "..\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,_legacy\*"
Source: "..\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.gitignore"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\tests\*"; DestDir: "{app}\tests"; Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,_legacy\*"
Source: "run_nmtbot.bat"; DestDir: "{app}"; Flags: ignoreversion
; Opcional: adicione icon.ico nesta pasta para personalizar os atalhos
Source: "install_deps.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\NMTBot"; Filename: "{app}\run_nmtbot.bat"; WorkingDir: {app}; IconFilename: "{app}\assets\nmt_bot_icon.ico"
Name: "{group}\Instalar Dependencias"; Filename: "{app}\install_deps.bat"; WorkingDir: {app}
Name: "{group}\Desinstalar NMTBot"; Filename: "{uninstallexe}"
Name: "{commondesktop}\NMTBot"; Filename: "{app}\run_nmtbot.bat"; WorkingDir: {app}; Tasks: desktopicon; IconFilename: "{app}\assets\nmt_bot_icon.ico"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Opcoes:"

[Code]
function PythonInstalled: Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/C py --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
  if not Result then
    Result := Exec(ExpandConstant('{cmd}'), '/C python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function InitializeSetup: Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if not PythonInstalled then
  begin
    if MsgBox('O Python 3.13+ nao foi encontrado no seu sistema.' #13#10 #13#10 'O NMTBot precisa do Python para funcionar.' #13#10 'Deseja abrir o site python.org para baixar e instalar manualmente?' #13#10 #13#10 'Apos instalar o Python, execute este instalador novamente.', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://www.python.org/downloads/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox('Instalacao concluida!' #13#10 #13#10 'Antes de usar o NMTBot pela primeira vez:' #13#10 '1. Abra o menu Iniciar -> NMTBot -> Instalar Dependencias' #13#10 '   (ou rode install_deps.bat na pasta do NMTBot)' #13#10 '2. Aguarde a instalacao das dependencias e do Chromium.' #13#10 '3. Depois, use o atalho NMTBot para iniciar o bot.' #13#10 #13#10 'Importante: faca login no nmt.gg na primeira execucao.', mbInformation, MB_OK);
  end;
end;

