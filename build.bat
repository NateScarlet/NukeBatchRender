CD /D "%~dp0"
SET "output=dist\batchrender-0.8.10.exe"
pyinstaller -F "batchrender.spec" 

MOVE /Y %~dp0dist\batchrender.exe %output%
%output%