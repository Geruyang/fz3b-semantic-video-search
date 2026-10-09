[CmdletBinding(DefaultParameterSetName = "Command")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "Command")]
    [string]$Command,

    [Parameter(Mandatory = $true, ParameterSetName = "Script")]
    [string]$Script,

    [Parameter(ParameterSetName = "Script", ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArguments
)

$ErrorActionPreference = "Stop"
$Python = "C:\Users\ruyangge\.codex\mcp\serial\.venv\Scripts\python.exe"
$DependencyRoot = Join-Path $PSScriptRoot "python312-ssh-deps"
$SshToolRoot = Join-Path (Split-Path $PSScriptRoot -Parent) "ps\tools\ssh"

foreach ($RequiredPath in @($Python, $DependencyRoot, $SshToolRoot)) {
    if (-not (Test-Path -LiteralPath $RequiredPath)) {
        throw "Required SSH runtime path is missing: $RequiredPath"
    }
}

$PreviousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$DependencyRoot;$SshToolRoot"
    if ($PSCmdlet.ParameterSetName -eq "Command") {
        & $Python -c $Command
    }
    else {
        & $Python $Script @ScriptArguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "SSH Python runtime exited with code $LASTEXITCODE"
    }
}
finally {
    $env:PYTHONPATH = $PreviousPythonPath
}
