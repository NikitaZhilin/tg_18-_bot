$ErrorActionPreference = "Stop"
$pythonProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*-m app*" }
if ($pythonProcesses) {
    $pythonProcesses | Select-Object ProcessId, Name, CommandLine
} else {
    Write-Output "Bot process not found"
}
