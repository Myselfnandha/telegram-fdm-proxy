Set objShell = CreateObject("WScript.Shell")
' Get the directory of the current script
strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
' Run the executable with a visible window and wait for it to finish
objShell.Run """" & strPath & "tg_fdm_proxy.exe""", 1, True
