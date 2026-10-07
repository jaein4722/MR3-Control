param(
    [string]$Python = (Join-Path $PSScriptRoot '..\.build-venv\Scripts\python.exe'),
    [string]$Iscc = (Join-Path $PSScriptRoot '..\build-tools\InnoSetup\ISCC.exe')
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = (Resolve-Path -LiteralPath $Python).Path
$Iscc = (Resolve-Path -LiteralPath $Iscc).Path
Push-Location $projectRoot
try {
    & $Python packaging/prepare_version.py
    if ($LASTEXITCODE -ne 0) { throw 'Invalid release version' }
    $version = (Get-Content -LiteralPath VERSION -Raw).Trim()
    & $Python -c "import tkinter; print('Tcl runtime:', tkinter.Tcl().eval('info patchlevel'))"
    if ($LASTEXITCODE -ne 0) { throw 'Tcl/Tk runtime unavailable; cannot build a working GUI package' }
    & $Python packaging/collect_licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
    & $Python -m PyInstaller --noconfirm --workpath build/pyinstaller packaging/MR3Control.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    $exe = Join-Path $projectRoot 'dist\MR3 Control\MR3 Control.exe'
    $report = Join-Path $projectRoot 'build\package-self-test.json'
    $check = Start-Process -FilePath $exe -ArgumentList @('--self-test', ('"' + $report + '"')) -WorkingDirectory (Join-Path $projectRoot 'build') -WindowStyle Hidden -Wait -PassThru
    if ($check.ExitCode -ne 0) { throw "Frozen runtime check failed. See $report" }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (-not $result.ok -or -not $result.frozen) { throw 'Invalid frozen runtime check result' }
    & $Iscc "/DAppVersion=$version" packaging/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
    $artifact = Join-Path $projectRoot "release\MR3-Control-$version-Setup-x64.exe"
    $hash = Get-FileHash -LiteralPath $artifact -Algorithm SHA256
    ($hash.Hash.ToLower() + '  ' + (Split-Path $artifact -Leaf)) | Set-Content (Join-Path $projectRoot 'release\SHA256SUMS.txt') -Encoding ascii
    Get-Item -LiteralPath $artifact | Select-Object FullName,Length
} finally {
    Pop-Location
}
