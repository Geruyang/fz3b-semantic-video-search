# Dot-source inside the dedicated task-tool PowerShell process before starting
# native tools. Never load into, or alter, the user's interactive application.
# Child processes inherit the process error mode unless they explicitly reset it.
# https://learn.microsoft.com/en-us/windows/win32/api/errhandlingapi/nf-errhandlingapi-seterrormode

function Enable-FzTaskToolErrorMode {
    if (-not ('FzTaskTools.NativeErrorMode' -as [type])) {
        Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
namespace FzTaskTools {
    public static class NativeErrorMode {
        [DllImport("kernel32.dll")]
        public static extern uint GetErrorMode();
        [DllImport("kernel32.dll")]
        public static extern uint SetErrorMode(uint mode);
    }
}
'@
    }
    [uint32] $previous = [FzTaskTools.NativeErrorMode]::GetErrorMode()
    # FAILCRITICALERRORS | NOGPFAULTERRORBOX | NOOPENFILEERRORBOX.
    # Do not add NOALIGNMENTFAULTEXCEPT: failures must remain observable.
    [uint32] $requested = $previous -bor 0x8003
    [void] [FzTaskTools.NativeErrorMode]::SetErrorMode($requested)
    if (([FzTaskTools.NativeErrorMode]::GetErrorMode() -band 0x8003) -ne 0x8003) {
        [void] [FzTaskTools.NativeErrorMode]::SetErrorMode($previous)
        throw 'Task process could not enable noninteractive error handling.'
    }
    return $previous
}

function Restore-FzTaskToolErrorMode {
    param([Parameter(Mandatory=$true)][uint32] $PreviousMode)
    [void] [FzTaskTools.NativeErrorMode]::SetErrorMode($PreviousMode)
}
