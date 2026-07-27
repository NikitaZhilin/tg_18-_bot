$ErrorActionPreference = "Stop"
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*-m app*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
