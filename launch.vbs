Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strBatPath = fso.BuildPath(strPath, "launch_minimized.bat")

If Not fso.FileExists(strBatPath) Then
    strBatPath = fso.BuildPath(strPath, "run.bat")
End If

If Not fso.FileExists(strBatPath) Then
    MsgBox "No se encontro un lanzador valido en:" & vbCrLf & strPath, vbCritical, "G360 Stock Monitor"
    WScript.Quit 1
End If

strCmd = "cmd.exe /c """ & strBatPath & """"
WshShell.Run strCmd, 7, False
