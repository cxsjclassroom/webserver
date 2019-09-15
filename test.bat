@ECHO OFF

SET PYTHONPATH=%~dp0\server;%~dp0\thirdparty

python -B %~dp0\test\test.py

@PAUSE
