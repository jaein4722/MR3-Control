# Official portable compiler, pinned by version and SHA-256. No system installation.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$toolsDir = Join-Path $root 'build-tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$installer = Join-Path $toolsDir 'innosetup-6.7.3.exe'
$expected = '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732'
if (-not (Test-Path -LiteralPath $installer)) {
    Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $installer
}
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expected) {
    throw 'Inno Setup installer checksum mismatch'
}
$destination = Join-Path $toolsDir 'InnoSetup'
$arguments = @('/PORTABLE=1', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/CURRENTUSER', '/NOICONS', '/NORESTART', '/TASKS=""', ('/DIR="' + $destination + '"'))
$process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Portable Inno Setup failed: $($process.ExitCode)" }
if (-not (Test-Path -LiteralPath (Join-Path $destination 'ISCC.exe'))) {
    throw 'ISCC.exe not found after portable setup'
}
