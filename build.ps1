param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'))
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Create the project virtual environment and install pyproject.toml dependencies first.'
}
& $projectPython -c 'import PyInstaller'
if ($LASTEXITCODE -ne 0) {
    throw 'Install the build tool with: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt'
}
& $projectPython -m PyInstaller --noconfirm --clean --distpath $OutputDirectory --workpath (Join-Path $PSScriptRoot 'build') (Join-Path $PSScriptRoot 'StargateDialer.spec')
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Write-Host "Executable: $(Join-Path $OutputDirectory 'StargateDialer.exe')"
