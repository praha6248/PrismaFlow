#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F0B7E2A-58C4-4C1E-9D2B-7A4E3F1C9B52}
AppName=PrismaFlow
AppVersion={#AppVersion}
AppPublisher=PrismaFlow
AppPublisherURL=https://github.com/praha6248/PrismaFlow
AppSupportURL=https://github.com/praha6248/PrismaFlow/issues
DefaultDirName={autopf}\PrismaFlow
DefaultGroupName=PrismaFlow
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\LICENSE
InfoBeforeFile=models.txt
OutputDir=..\..\dist
OutputBaseFilename=PrismaFlow-{#AppVersion}-windows-x64-setup
SetupIconFile=..\prismaflow.ico
UninstallDisplayIcon={app}\PrismaFlow.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\PrismaFlow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PrismaFlow"; Filename: "{app}\PrismaFlow.exe"
Name: "{group}\Ollama download page"; Filename: "https://ollama.com/download"
Name: "{autodesktop}\PrismaFlow"; Filename: "{app}\PrismaFlow.exe"; Tasks: desktopicon

[Run]
Filename: "https://ollama.com/download"; Description: "Open the Ollama download page"; Flags: postinstall shellexec skipifsilent unchecked
Filename: "{app}\PrismaFlow.exe"; Description: "{cm:LaunchProgram,PrismaFlow}"; Flags: postinstall nowait skipifsilent
