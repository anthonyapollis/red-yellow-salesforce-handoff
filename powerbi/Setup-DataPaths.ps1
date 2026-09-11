$ErrorActionPreference = 'Stop'
$dataRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'data')).Path
$tables = Join-Path $PSScriptRoot 'RedAndYellow.SemanticModel\definition\tables'
$count = 0
Get-ChildItem -LiteralPath $tables -Filter '*.tmdl' | ForEach-Object {
    $file = $_.FullName
    $text = [IO.File]::ReadAllText($file)
    $updated = [regex]::Replace($text, 'File\.Contents\("([^"]+\.parquet)"\)', {
        param($match)
        $leaf = ($match.Groups[1].Value -split '[\\/]')[-1]
        $resolved = Join-Path $dataRoot $leaf
        if (!(Test-Path -LiteralPath $resolved -PathType Leaf)) { throw "Missing data file: $resolved" }
        'File.Contents("' + $resolved.Replace('"','""') + '")'
    })
    if ($text -match 'File\.Contents') { $script:count++ }
    [IO.File]::WriteAllText($file, $updated, [Text.UTF8Encoding]::new($false))
}
Write-Host "Configured $count tables for $dataRoot"
Write-Host 'Open RedAndYellow.pbip, then click Refresh. Close the old report without saving first.'