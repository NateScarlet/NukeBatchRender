CD /D "%~dp0"
SET "output=dist\batchrender-0.9.1.exe"
pyinstaller -F "batchrender.spec" 

MOVE /Y %~dp0dist\batchrender.exe %output%
%output%