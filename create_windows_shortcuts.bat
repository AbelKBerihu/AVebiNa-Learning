@echo off
set SCRIPT_DIR=%~dp0
echo Creating Windows Desktop Shortcuts for LearnEcho and CrossSync...

powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\LearnEcho.lnk'); $Shortcut.TargetPath = 'pythonw.exe'; $Shortcut.Arguments = '\"%SCRIPT_DIR%run_learner.py\"'; $Shortcut.WorkingDirectory = '%SCRIPT_DIR%'; $Shortcut.Description = 'LearnEcho AI Study Companion'; $Shortcut.Save()"
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\CrossSync.lnk'); $Shortcut.TargetPath = 'pythonw.exe'; $Shortcut.Arguments = '\"%SCRIPT_DIR%main.py\"'; $Shortcut.WorkingDirectory = '%SCRIPT_DIR%'; $Shortcut.Description = 'CrossSync Notes'; $Shortcut.Save()"

echo Done! Shortcuts created on your Windows Desktop.
pause
