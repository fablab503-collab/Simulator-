# Takes a screenshot of the whole Windows desktop and saves the Windows
# version next to it. Works on any Windows PC and on GitHub's Windows runners.
param([string]$OutDir = "screenshots")

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Save which Windows version this is, so you can see it in the results.
Get-ComputerInfo -Property OsName, OsVersion, OsBuildNumber |
  Format-List | Out-File (Join-Path $OutDir "windows-version.txt")

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

$path = Join-Path (Resolve-Path $OutDir) "windows-desktop.png"
$bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()

Write-Host "Saved $path ($($bounds.Width)x$($bounds.Height))"
