<#
 .SYNOPSIS
 Starts the Jewel AI development server with virtual environment activation.

 .DESCRIPTION
 This script navigates to the project root, activates the Python venv, and launches
 the FastAPI server using Uvicorn with reload enabled.
#>
param(
	[string] $Domain = "",
	[switch] $Https,
	[string] $CertFile = "",
	[string] $KeyFile = "",
	[int] $Port = 8000,
	[switch] $NoReload,
	[switch] $AddHosts
)

# Save current location and move to script directory
Push-Location -Path $PSScriptRoot

# Activate the Python virtual environment (dot-source for this session)
. "$PSScriptRoot\.venv\Scripts\Activate.ps1"

# Build uvicorn arguments
# Use a different variable name than the automatic $Host variable provided by PowerShell
$bindHost = '0.0.0.0'
$args = @('-m','uvicorn','server.app:app','--host',$bindHost,'--port',$Port)
if (-not $NoReload) { $args += '--reload' }

if ($Https) {
	if (-not $CertFile -or -not $KeyFile) {
		Write-Host "HTTPS requested but CertFile/KeyFile not provided. Set -CertFile and -KeyFile or run without -Https." -ForegroundColor Yellow
	} else {
		$args += @('--ssl-certfile',$CertFile,'--ssl-keyfile',$KeyFile)
	}
}

if ($Domain) {
	Write-Host "Starting server for domain: $Domain on port $Port"
} else {
	# Use explicit variable delimiters so PowerShell doesn't interpret $bindHost:$Port as an invalid variable token
	Write-Host "Starting server on ${bindHost}:${Port}"
}

# Optional: add hosts file entry (requires elevation). This is attempted only if -AddHosts is supplied.
if ($AddHosts -and $Domain) {
	$hostsPath = "$env:windir\System32\drivers\etc\hosts"
	try {
		# Backup hosts file
		Copy-Item -Path $hostsPath -Destination "$hostsPath.bak" -Force -ErrorAction Stop
		$entry = "127.0.0.1`t$Domain"
		Add-Content -Path $hostsPath -Value $entry -ErrorAction Stop
		Write-Host "Added hosts entry: $entry" -ForegroundColor Green
	} catch {
		Write-Host "Could not add hosts entry automatically. Run PowerShell as Administrator and add '127.0.0.1 $Domain' to your hosts file." -ForegroundColor Yellow
	}
}

# Launch the FastAPI server
try {
	# Use argument splatting so the python executable receives the array of args correctly
	& .\.venv\Scripts\python.exe @args
} finally {
	# Return to original location when the script exits
	Pop-Location
}