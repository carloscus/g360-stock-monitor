Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strCurrentPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
strDesktop = objShell.SpecialFolders("Desktop")
strBatPath = strCurrentPath & "\run.bat"
strIconPath = strCurrentPath & "\assets\images\cipsa.ico"

' Eliminar acceso directo anterior si existe
If objFSO.FileExists(strDesktop & "\G360 Stock Monitor.lnk") Then
    objFSO.DeleteFile strDesktop & "\G360 Stock Monitor.lnk", True
End If

Set objShortcut = objShell.CreateShortcut(strDesktop & "\G360 Stock Monitor.lnk")
objShortcut.TargetPath = strBatPath
objShortcut.WorkingDirectory = strCurrentPath
objShortcut.Description = "G360 Stock Monitor - Monitoreo de stock CIPSA"
objShortcut.WindowStyle = 7  ' 7=Minimized, 1=Normal, 3=Maximized

If objFSO.FileExists(strIconPath) Then
    objShortcut.IconLocation = strIconPath & ", 0"
Else
    objShortcut.IconLocation = "%SystemRoot%\system32\shell32.dll, 15"
End If

objShortcut.Save

' Refrescar cache de iconos del escritorio
objShell.Run "ie4uinit.exe -show", 0, True
