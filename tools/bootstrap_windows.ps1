$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root "runtime"
$PythonDir = Join-Path $Runtime "python"
$PythonExe = Join-Path $PythonDir "python.exe"
$ZipPath = Join-Path $Runtime "python-embed.zip"
$GetPip = Join-Path $Runtime "get-pip.py"

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

if (!(Test-Path $PythonExe)) {
    Write-Host "Downloading Python embeddable runtime..."
    $Url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip"
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $PythonDir -Force
    $Pth = Get-ChildItem $PythonDir -Filter "*._pth" | Select-Object -First 1
    if ($Pth) {
        $Content = Get-Content $Pth.FullName
        $Content = $Content | ForEach-Object {
            if ($_ -eq "#import site") { "import site" } else { $_ }
        }
        Set-Content -Path $Pth.FullName -Value $Content -Encoding ASCII
    }
}

if (!(Test-Path $GetPip)) {
    Write-Host "Downloading pip bootstrap..."
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
}

& $PythonExe $GetPip
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $Root "requirements.txt")
& $PythonExe -m pip install -e $Root
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Runtime "ms-playwright"
& $PythonExe -m playwright install chromium

Write-Host "Done. Use run_windows.bat to run the tool."
