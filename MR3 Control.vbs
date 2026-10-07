Option Explicit
Dim shell, fso, folder, python, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
python = folder & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(python) Then
  python = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
End If
If Not fso.FileExists(python) Then
  MsgBox "Python not found. See README.md for setup.", 16, "MR3 Control"
  WScript.Quit 1
End If
shell.CurrentDirectory = folder
command = Chr(34) & python & Chr(34) & " " & Chr(34) & folder & "\mr3_app.py" & Chr(34)
shell.Run command, 0, False
