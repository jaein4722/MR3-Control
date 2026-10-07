param(
    [ValidateSet('scan', 'inspect', 'identify', 'status')][string]$Mode = 'scan',
    [string]$Address,
    [ValidateRange(1, 60)][int]$Seconds = 15,
    [string]$PythonPath
)
$ErrorActionPreference = 'Stop'
if (-not $PythonPath) {
    $taskBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $taskBundledPython) { $PythonPath = $taskBundledPython }
    else {
        $taskPython = Get-Command python -ErrorAction SilentlyContinue
        if ($taskPython -and $taskPython.Source -notlike '*\WindowsApps\*') {
            $PythonPath = $taskPython.Source
        }
    }
}
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
    throw 'Python not found. Specify -PythonPath with a Python 3.11+ executable.'
}
$taskArgs = @((Join-Path $PSScriptRoot 'mr3_diagnostics.py'), $Mode, '--seconds', $Seconds)
if ($Address) { $taskArgs += @('--address', $Address) }
& $PythonPath @taskArgs
exit $LASTEXITCODE
