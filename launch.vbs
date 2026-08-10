Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strFile = fso.BuildPath(strPath, "run.bat")
WshShell.Run chr(34) & strFile & Chr(34), 7, False
