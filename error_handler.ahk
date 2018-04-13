#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
#Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.
#SingleInstance force

WinGet, CurrentWin, ID, A
Loop {
	PrevWin := CurrentWin
    WinGet, CurrentWin, ID, A
	If (CurrentWin != PrevWin) {
	    OnWinChange()
	}
}

OnWinChange()
{
    IfWinExist, ahk_exe WerFault.exe,
		sleep, 3000
        WinClose,
	IfWinExist, ahk_exe CrashReporterNuke.exe,
		WinClose,
	IfWinExist, Optical Flares License ahk_class VCWINDOW ahk_exe Nuke10.5.exe,
		WinClose,
	IfWinExist, mayabatch.exe ahk_class #32770 ahk_exe , .dll
		WinClose,
}
