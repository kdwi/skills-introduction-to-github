param(
    [switch]$Clean,
    [switch]$IncludeHibernation
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host '正在申请管理员权限，请在弹窗中点“是”...' -ForegroundColor Yellow
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    if ($Clean) { $argList += '-Clean' }
    if ($IncludeHibernation) { $argList += '-IncludeHibernation' }
    Start-Process powershell -Verb RunAs -ArgumentList $argList
    exit
}

function Format-Size([double]$Bytes) {
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N1} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N0} KB' -f ($Bytes / 1KB)) }
    return ('{0:N0} B' -f $Bytes)
}

function Get-PathSize([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return [double]0 }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer) { return [double]$item.Length }
    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { return [double]0 }
    return [double]$sum
}

function Get-FreeSpace {
    $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    return [double]$d.FreeSpace
}

function Clear-FolderContents([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeBefore = [double]$drive.FreeSpace
$total = [double]$drive.Size

Write-Host ''
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '                C 盘空间分析与清理' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ('C 盘总容量 : {0}' -f (Format-Size $total))
Write-Host ('当前可用   : {0}  ({1:N1}% 空闲)' -f (Format-Size $freeBefore), ($freeBefore / $total * 100))
Write-Host ''

$targets = @(
    @{ Name = '用户临时文件';       Path = $env:TEMP },
    @{ Name = '系统临时文件';       Path = "$env:windir\Temp" },
    @{ Name = 'Windows 更新缓存';   Path = "$env:windir\SoftwareDistribution\Download" },
    @{ Name = '传递优化缓存';       Path = "$env:windir\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization" },
    @{ Name = '错误报告缓存';       Path = "$env:ProgramData\Microsoft\Windows\WER" },
    @{ Name = '缩略图/图标缓存';    Path = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer" },
    @{ Name = 'DirectX 着色器缓存'; Path = "$env:LOCALAPPDATA\D3DSCache" }
)

Write-Host '【可清理项】' -ForegroundColor Green
$totalCleanable = [double]0
foreach ($t in $targets) {
    $size = Get-PathSize $t.Path
    $totalCleanable += $size
    $exists = Test-Path -LiteralPath $t.Path
    Write-Host ('  {0,-16} {1,10}   {2}' -f $t.Name, (Format-Size $size),
        $(if ($exists) { $t.Path } else { '不存在' }))
}
Write-Host ('  {0,-16} {1,10}' -f '合计', (Format-Size $totalCleanable)) -ForegroundColor Green
Write-Host ''

Write-Host '【其他占用（需手动处理）】' -ForegroundColor Yellow
$manual = @(
    @{ Name = '休眠文件 hiberfil.sys'; Path = "$env:SystemDrive\hiberfil.sys" },
    @{ Name = '虚拟内存 pagefile.sys'; Path = "$env:SystemDrive\pagefile.sys" },
    @{ Name = '旧系统 Windows.old';    Path = "$env:SystemDrive\Windows.old" }
)
foreach ($m in $manual) {
    if (Test-Path -LiteralPath $m.Path) {
        $size = Get-PathSize $m.Path
        Write-Host ('  {0,-24} {1,10}' -f $m.Name, (Format-Size $size))
    }
}
if (Test-Path -LiteralPath "$env:windir\WinSxS") {
    Write-Host '  组件存储 WinSxS          请用 DISM 清理，切勿手动删除'
}
Write-Host ''

if (-not $Clean) {
    Write-Host '当前为“仅扫描”模式，没有删除任何文件。' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '确认后执行清理（管理员 PowerShell）：' -ForegroundColor White
    Write-Host '  powershell -NoProfile -ExecutionPolicy Bypass -File ".\清理C盘.ps1" -Clean'
    Write-Host '如需同时关闭休眠、释放与内存等大的 hiberfil.sys：'
    Write-Host '  powershell -NoProfile -ExecutionPolicy Bypass -File ".\清理C盘.ps1" -Clean -IncludeHibernation'
    Write-Host ''
    Read-Host '按回车键退出'
    exit
}

Write-Host '开始清理安全项...' -ForegroundColor Cyan

Clear-FolderContents $env:TEMP
Clear-FolderContents "$env:windir\Temp"
Clear-FolderContents "$env:ProgramData\Microsoft\Windows\WER\ReportArchive"
Clear-FolderContents "$env:ProgramData\Microsoft\Windows\WER\ReportQueue"
Clear-FolderContents "$env:LOCALAPPDATA\D3DSCache"

Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\Microsoft\Windows\Explorer" -Filter 'thumbcache_*.db' -Force -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\Microsoft\Windows\Explorer" -Filter 'iconcache_*.db' -Force -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

Clear-RecycleBin -DriveLetter C -Force -ErrorAction SilentlyContinue

Stop-Service -Name wuauserv, bits -Force -ErrorAction SilentlyContinue
Clear-FolderContents "$env:windir\SoftwareDistribution\Download"
Start-Service -Name wuauserv, bits -ErrorAction SilentlyContinue

if (Get-Command Delete-DeliveryOptimizationCache -ErrorAction SilentlyContinue) {
    Delete-DeliveryOptimizationCache -Force -ErrorAction SilentlyContinue
}

if ($IncludeHibernation) {
    Write-Host '正在关闭休眠并删除 hiberfil.sys...' -ForegroundColor Yellow
    powercfg /h off
}

$freeAfter = Get-FreeSpace
$freed = $freeAfter - $freeBefore

Write-Host ''
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ('清理前可用 : {0}' -f (Format-Size $freeBefore))
Write-Host ('清理后可用 : {0}' -f (Format-Size $freeAfter))
Write-Host ('本次释放   : {0}' -f (Format-Size $freed)) -ForegroundColor Green
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host '进一步释放空间（可选，管理员 PowerShell）：' -ForegroundColor Yellow
Write-Host '  组件存储清理 : Dism.exe /Online /Cleanup-Image /StartComponentCleanup'
Write-Host '  系统磁盘清理 : cleanmgr /d C:'
Write-Host '  查看大文件   : 推荐使用免费的 WizTree 或 TreeSize 扫描 C 盘'
Write-Host ''
Read-Host '按回车键退出'
