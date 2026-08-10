Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strCurrentPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
strDesktop = objShell.SpecialFolders("Desktop")
strBatPath = strCurrentPath & "\run.bat"
strIconPath = strCurrentPath & "\assets\images\cipsa.ico"

If Not objFSO.FileExists(strBatPath) Then
    MsgBox "No se encontro run.bat en:" & vbCrLf & strCurrentPath, vbCritical, "G360 Stock Monitor"
    WScript.Quit 1
End If

strShortcutPath = strDesktop & "\G360 Stock Monitor.lnk"

If objFSO.FileExists(strShortcutPath) Then
    objFSO.DeleteFile strShortcutPath, True
End If

Set objShortcut = objShell.CreateShortcut(strShortcutPath)
objShortcut.TargetPath = strBatPath
objShortcut.WorkingDirectory = strCurrentPath
objShortcut.Description = "G360 Stock Monitor - Monitoreo de stock CIPSA"
objShortcut.WindowStyle = 7

If objFSO.FileExists(strIconPath) Then
    objShortcut.IconLocation = strIconPath & ", 0"
Else
    objShortcut.IconLocation = "%SystemRoot%\system32\shell32.dll, 15"
End If

objShortcut.Save

objShell.Run "ie4uinit.exe -show", 0, True

