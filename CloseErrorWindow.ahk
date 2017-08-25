#SingleInstance Force

Loop {
    IfWinExist, ahk_exe WerFault.exe,
        WinClose,
	IfWinExist, ahk_exe CrashReporterNuke.exe,
		WinClose,
	Sleep, 1000
}