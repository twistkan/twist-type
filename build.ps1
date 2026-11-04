param([switch]$InstallDependencies)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python 3.14 virtual environment.' }
}
if ($InstallDependencies) {
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $python assets/generate_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
$savedBuildPath = $env:PATH
try {
    # Qt links to Windows ICU. Unrelated media tools on PATH may ship an
    # incompatible icuuc.dll/ucrtbase.dll which PyInstaller would otherwise collect.
    $basePython = & $python -c 'import sys; print(sys.base_prefix)'
    $env:PATH = "$PSScriptRoot\.venv\Scripts;$basePython;$basePython\DLLs;$env:WINDIR\System32;$env:WINDIR"
    & $python -m PyInstaller --noconfirm --clean --onefile --noconsole --noupx --optimize 1 --name TwistType --icon assets/twisttype.ico --add-data 'assets/twisttype.ico:assets' --add-data 'snippets.yaml:.' --add-data 'assets/licenses:licenses' --add-data 'THIRD-PARTY.md:.' --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf --exclude-module tkinter twisttype.py
    $buildExit = $LASTEXITCODE
} finally {
    $env:PATH = $savedBuildPath
}
if ($buildExit -ne 0) { throw 'Executable build failed.' }
$release = Join-Path $PSScriptRoot 'release\TwistType'
New-Item -ItemType Directory -Path $release -Force | Out-Null
try {
    Copy-Item -LiteralPath 'dist\TwistType.exe' -Destination $release -Force
} catch {
    # A running onefile image can be renamed while its current session continues.
    # Preserve it and install the update without terminating unsaved editor work.
    $previous = Join-Path $PSScriptRoot 'release\previous'
    New-Item -ItemType Directory -Path $previous -Force | Out-Null
    $backupName = 'TwistType-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.exe'
    Move-Item -LiteralPath (Join-Path $release 'TwistType.exe') -Destination (Join-Path $previous $backupName)
    Copy-Item -LiteralPath 'dist\TwistType.exe' -Destination $release -Force
}
if (!(Test-Path -LiteralPath (Join-Path $release 'snippets.yaml'))) {
    Copy-Item -LiteralPath 'snippets.yaml' -Destination $release
}
Copy-Item -LiteralPath 'README.md' -Destination $release -Force
Copy-Item -LiteralPath 'THIRD-PARTY.md' -Destination $release -Force
if (Test-Path -LiteralPath 'VALIDATION.md') {
    Copy-Item -LiteralPath 'VALIDATION.md' -Destination $release -Force
}
$licenses = Join-Path $release 'licenses'
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
Copy-Item -Path 'assets\licenses\*.txt' -Destination $licenses -Force
Get-ChildItem -Path '.venv\Lib\site-packages\pyside6_essentials-*.dist-info', '.venv\Lib\site-packages\shiboken6-*.dist-info', '.venv\Lib\site-packages\pyyaml-*.dist-info' -Directory | ForEach-Object {
    $licenseSource = Join-Path $_.FullName 'licenses'
    if (Test-Path -LiteralPath $licenseSource) {
        Copy-Item -LiteralPath $licenseSource -Destination (Join-Path $licenses $_.Name) -Recurse -Force
    }
}
$pythonLicense = & $python -c "import pathlib,sys; print(pathlib.Path(sys.base_prefix) / 'LICENSE.txt')"
if (Test-Path -LiteralPath $pythonLicense) {
    Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $licenses 'PYTHON-LICENSE.txt')
}
& $python package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
Write-Host "Single EXE ready: $PSScriptRoot\release\Single-EXE\TwistType.exe"
