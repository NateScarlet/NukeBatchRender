REM CD /D "%UserProfile%"
CD /D "%~dp0"
REM MKDIR NukeBatchRender
REM CD NukeBatchRender

pyinstaller.exe -F "%~dp0batchrender.py" --distpath .
%~dp0batchrender.exe
REM CD dist
REM "C:\Program Files\7-Zip\7z.exe" a -r0 "..\Nuke批渲染_v.zip" "*"
REM CD ..
REM EXPLORER %CD%