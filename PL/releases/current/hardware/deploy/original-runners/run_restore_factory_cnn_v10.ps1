[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$EvidenceDir,[string]$VivadoRoot='D:\Vivado\2026.1\Vivado')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
function Sha([string]$p){
    for($attempt=1;$attempt-le20;$attempt++){
        try{return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
        catch [System.IO.IOException]{
            if($attempt-eq20){throw}
            Start-Sleep -Milliseconds 250
        }
    }
    throw "Unreachable SHA256 retry state for $p"
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'));$factory=Join-Path $root 'artifacts\board-debug-20261007\acceleration\host\network10-v10.1-platform-deployment-001\recovery\factory-restore-native.bin';$tcl=Join-Path $PSScriptRoot 'restore_factory_cnn_v10.tcl';$vivado=Join-Path $VivadoRoot 'bin\vivado.bat';$hw=Join-Path $VivadoRoot 'bin\hw_server.bat';$e=[IO.Path]::GetFullPath($EvidenceDir)
if((Sha $factory)-ne'59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e'){throw 'Factory SHA mismatch'};if(Test-Path $e){throw 'EvidenceDir must be new'};if(@(Get-Process vivado,vitis_hls,vitis-run,v++,xcd -ErrorAction SilentlyContinue).Count){throw 'AMD tool slot occupied'}
New-Item -ItemType Directory $e|Out-Null;$pa=Join-Path $e 'private-appdata';$pl=Join-Path $e 'private-appdata-local';New-Item -ItemType Directory $pa,$pl|Out-Null;$envs=@{APPDATA=$pa;LOCALAPPDATA=$pl};$out=Join-Path $e 'vivado.stdout.log';$err=Join-Path $e 'vivado.stderr.log';$hso=Join-Path $e 'hw_server.stdout.log';$hse=Join-Path $e 'hw_server.stderr.log';$owned=$null
if(!(Test-NetConnection localhost -Port 3121 -InformationLevel Quiet -WarningAction SilentlyContinue)){$owned=Start-Process $hw -ArgumentList @('-s','tcp::3121') -WindowStyle Hidden -PassThru -RedirectStandardOutput $hso -RedirectStandardError $hse -Environment $envs;for($i=0;$i-lt20;$i++){Start-Sleep -Milliseconds 500;if(Test-NetConnection localhost -Port 3121 -InformationLevel Quiet -WarningAction SilentlyContinue){break}}}
# Let cmd.exe own the redirection handles.  WaitForExit then means both the
# Vivado batch wrapper and its redirected stdout/stderr handles are closed;
# Start-Process -RedirectStandardOutput could leave the file locked after a
# successful hardware operation and make receipt hashing fail.
$psi=[Diagnostics.ProcessStartInfo]::new();$psi.FileName=$env:ComSpec
$psi.Arguments='/d /s /c ""'+$vivado+'" -mode batch -source "'+$tcl+'" -nojournal -nolog -notrace -tclargs "'+$factory+'" 1>"'+$out+'" 2>"'+$err+'""'
$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
foreach($key in $envs.Keys){$psi.Environment[$key]=$envs[$key]}
$p=[Diagnostics.Process]::Start($psi);try{$p.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal}catch{};$p.WaitForExit();$vivadoExitCode=$p.ExitCode;$p.Dispose();if($null-ne$owned-and!$owned.HasExited){$owned.Kill($true);$owned.WaitForExit()};Start-Sleep -Seconds 2
$pass=($vivadoExitCode-eq0)-and(Select-String -LiteralPath $out -SimpleMatch 'CNN_V10_FACTORY_RESTORE_END RC=0 FACTORY_RESTORED=1' -Quiet);$r=[ordered]@{schema='cnn-v10-factory-restore-v1';pass=$pass;exit_code=$vivadoExitCode;command='program_hw_devices -mpsoc_reset no';factory=[ordered]@{path=$factory;bytes=(Get-Item $factory).Length;sha256=Sha $factory};source=[ordered]@{tcl_sha256=Sha $tcl;runner_sha256=Sha $MyInvocation.MyCommand.Path};stdout_sha256=Sha $out;stderr_sha256=Sha $err};$r|ConvertTo-Json -Depth 8|Set-Content (Join-Path $e 'receipt.json') -Encoding utf8;if(!$pass){throw 'Factory restore failed'};Write-Output($r|ConvertTo-Json -Depth 8 -Compress)
