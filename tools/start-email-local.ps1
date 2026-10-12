param(
    [string]$GhuntSessionFile = (Join-Path $env:USERPROFILE '.malfrats\ghunt\creds.m'),
    [string]$BackendPython = 'C:\Users\91966\anaconda3\python.exe'
)

$ErrorActionPreference = 'Stop'
$taskWorkspace = Split-Path $PSScriptRoot -Parent
$taskGhuntPython = Join-Path $taskWorkspace 'output\ghunt-runtime-modern\Scripts\python.exe'
if (!(Test-Path -LiteralPath $BackendPython -PathType Leaf)) {
    throw 'Backend Python not found. Pass -BackendPython with your interpreter path.'
}
if (!(Test-Path -LiteralPath $taskGhuntPython -PathType Leaf)) {
    throw 'Isolated GHunt runtime not installed. See docs/email-open-source-stack.md.'
}

$env:FLASK_ENV = 'development'
$env:FLASK_DEBUG = '0'
$env:PORT = '5000'
$env:EMAIL_LINKEDIN_PUBLIC_ENABLED = 'true'
$env:EMAIL_GHUNT_ENABLED = 'true'
$env:EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED = 'true'
$env:GHUNT_PYTHON_EXECUTABLE = $taskGhuntPython
$env:GHUNT_SESSION_FILE = $GhuntSessionFile
if (!(Test-Path -LiteralPath $GhuntSessionFile -PathType Leaf)) {
    Write-Host 'GHunt login is pending; the dashboard will report unconfigured.'
    Write-Host 'Run output\ghunt-runtime-modern\Scripts\ghunt.exe login locally, then restart this backend.'
}

Push-Location (Join-Path $taskWorkspace 'backend')
try {
    & $BackendPython app.py
} finally {
    Pop-Location
}
