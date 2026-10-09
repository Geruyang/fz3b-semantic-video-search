# Read-only Windows memory checks at task launch / stage boundaries.
# User policy: strengthen monitoring and restrict new heavy concurrency only at
# >=90%.  Owned heavy-tool launchers may retain an explicit free-RAM budget.
# All values are GiB (2^30 bytes); no pagefile/system setting is changed.
function Get-FzTaskMemorySnapshot {
    if (-not ('FzTaskTools.NativeMemory' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace FzTaskTools {
    [StructLayout(LayoutKind.Sequential)]
    public struct MemoryStatus {
        public uint Length, MemoryLoad;
        public ulong TotalPhys, AvailPhys, TotalPageFile, AvailPageFile;
        public ulong TotalVirtual, AvailVirtual, AvailExtendedVirtual;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct PerformanceInfo {
        public uint Size;
        public UIntPtr CommitTotal, CommitLimit, CommitPeak;
        public UIntPtr PhysicalTotal, PhysicalAvailable, SystemCache;
        public UIntPtr KernelTotal, KernelPaged, KernelNonpaged, PageSize;
        public uint HandleCount, ProcessCount, ThreadCount;
    }
    public static class NativeMemory {
        [DllImport("kernel32.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GlobalMemoryStatusEx(ref MemoryStatus status);
        [DllImport("psapi.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetPerformanceInfo(ref PerformanceInfo info, uint size);
    }
}
'@
    }
    $status = New-Object FzTaskTools.MemoryStatus
    $status.Length = [System.Runtime.InteropServices.Marshal]::SizeOf($status)
    if (-not [FzTaskTools.NativeMemory]::GlobalMemoryStatusEx([ref]$status)) {
        throw 'Cannot measure memory; do not start another heavy task.'
    }
    # GlobalMemoryStatusEx's pagefile fields can reflect the current process's
    # Job limit. Use system-wide commit figures even inside a limited launcher.
    $performance = New-Object FzTaskTools.PerformanceInfo
    $performance.Size = [System.Runtime.InteropServices.Marshal]::SizeOf($performance)
    if (-not [FzTaskTools.NativeMemory]::GetPerformanceInfo([ref]$performance, $performance.Size)) {
        throw 'Cannot measure system commit headroom; defer heavy work.'
    }
    $pageBytes = $performance.PageSize.ToUInt64()
    $commitLimit = $performance.CommitLimit.ToUInt64() * $pageBytes
    $commitHeadroom = ($performance.CommitLimit.ToUInt64() - $performance.CommitTotal.ToUInt64()) * $pageBytes
    [pscustomobject]@{
        timestamp = (Get-Date -Format o)
        total_physical_gib = $status.TotalPhys / 1GB
        available_physical_gib = $status.AvailPhys / 1GB
        commit_limit_gib = $commitLimit / 1GB
        commit_headroom_gib = $commitHeadroom / 1GB
        memory_load_percent = $status.MemoryLoad
        concurrency_limited = ($status.MemoryLoad -ge 90)
        intensive_monitoring_required = ($status.MemoryLoad -ge 90)
        pressure = ($status.MemoryLoad -ge 95)
    }
}

function Assert-FzTaskMemoryForLaunch {
    param(
        [double] $MinimumPhysicalGiB = 0,
        [double] $MinimumCommitGiB = 0
    )
    $snapshot = Get-FzTaskMemorySnapshot
    if ($snapshot.concurrency_limited) {
        throw ('New heavy launch deferred: physical memory usage {0}% is at or above the user 90% threshold.' -f $snapshot.memory_load_percent)
    }
    if ($MinimumPhysicalGiB -gt 0 -and $snapshot.available_physical_gib -lt $MinimumPhysicalGiB) {
        throw ('New heavy launch deferred: available physical memory {0:F3} GiB is below the required {1:F3} GiB budget.' -f $snapshot.available_physical_gib,$MinimumPhysicalGiB)
    }
    if ($MinimumCommitGiB -gt 0 -and $snapshot.commit_headroom_gib -lt $MinimumCommitGiB) {
        throw ('New heavy launch deferred: commit headroom {0:F3} GiB is below the required {1:F3} GiB budget.' -f $snapshot.commit_headroom_gib,$MinimumCommitGiB)
    }
    return $snapshot
}
