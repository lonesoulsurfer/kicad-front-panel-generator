@echo off
rem Opens the Panel Generator window. Double-click this file.
where pyw >nul 2>nul && (start "" pyw "%~dp0panelgen_gui.pyw" %* & exit /b)
start "" py "%~dp0panelgen_gui.pyw" %*
