Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)

' --- First run: show visible console for setup progress ---
If fso.FolderExists(fso.BuildPath(strPath, ".venv")) And _
   fso.FileExists(fso.BuildPath(strPath, ".venv\Scripts\python.exe")) Then
    ' Venv already exists: launch minimized (console visible in taskbar on errors)
    strBatPath = fso.BuildPath(strPath, "launch_minimized.bat")
    If fso.FileExists(strBatPath) Then
        WshShell.Run "cmd.exe /c """ & strBatPath & """", 6, False
    Else
        WshShell.Run "cmd.exe /c """ & fso.BuildPath(strPath, "run.bat") & """", 6, False
    End If
Else
    ' First run: show visible console so user sees install progress
    strBatPath = fso.BuildPath(strPath, "run.bat")
    If fso.FileExists(strBatPath) Then
        WshShell.Run "cmd.exe /c """ & strBatPath & """", 1, True
    Else
        MsgBox "No se encontro run.bat en:" & vbCrLf & strPath, vbCritical, "G360 Stock Monitor"
        WScript.Quit 1
    End If
End If
