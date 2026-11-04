param([string]$ToolRoot = '', [string]$JavaHome = '', [string]$AndroidJar = '', [string]$BuildTools = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!$ToolRoot) {
    $localTools = Join-Path $PSScriptRoot 'tools'
    $cachedTools = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'MobileTrans App\tools'
    if (Test-Path -LiteralPath (Join-Path $localTools 'java')) { $ToolRoot = $localTools } else { $ToolRoot = $cachedTools }
}
if (!$JavaHome) {
    if ($env:JAVA_HOME) { $JavaHome = $env:JAVA_HOME }
    else { $JavaHome = (Get-ChildItem -LiteralPath (Join-Path $ToolRoot 'java') -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName }
}
if (!$AndroidJar) { $AndroidJar = Join-Path $ToolRoot 'sdk\platform\android-35\android.jar' }
if (!$BuildTools) { $BuildTools = Join-Path $ToolRoot 'sdk\build-tools\android-15' }
$java = Join-Path $JavaHome 'bin\java.exe'
$javac = Join-Path $JavaHome 'bin\javac.exe'
$jar = Join-Path $JavaHome 'bin\jar.exe'
$keytool = Join-Path $JavaHome 'bin\keytool.exe'
$aapt = Join-Path $BuildTools 'aapt2.exe'
$align = Join-Path $BuildTools 'zipalign.exe'
foreach ($required in @($java,$javac,$jar,$keytool,$AndroidJar,$aapt,$align,(Join-Path $BuildTools 'lib\d8.jar'),(Join-Path $BuildTools 'lib\apksigner.jar'))) {
    if (!(Test-Path -LiteralPath $required)) { throw "Missing build tool: $required" }
}
$run = Join-Path $PSScriptRoot ('build\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$classes = Join-Path $run 'classes'
$generated = Join-Path $run 'generated'
$dex = Join-Path $run 'dex'
$testClasses = Join-Path $run 'test-classes'
foreach ($path in @($run,$classes,$generated,$dex,$testClasses)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
& $javac -encoding UTF-8 --release 8 -d $testClasses 'src\com\twisttype\android\Logic.java' 'tests\com\twisttype\android\LogicTest.java'
if ($LASTEXITCODE -ne 0) { throw 'Core test compilation failed.' }
& $java -cp $testClasses com.twisttype.android.LogicTest
if ($LASTEXITCODE -ne 0) { throw 'Android core tests failed.' }
$compiled = Join-Path $run 'resources.zip'
& $aapt compile --dir res -o $compiled
if ($LASTEXITCODE -ne 0) { throw 'Resource compilation failed.' }
$base = Join-Path $run 'base.apk'
& $aapt link -o $base -I $AndroidJar --manifest AndroidManifest.xml --java $generated --min-sdk-version 26 --target-sdk-version 28 --version-code 3 --version-name 1.0.2 --auto-add-overlay $compiled
if ($LASTEXITCODE -ne 0) { throw 'Resource linking failed.' }
$utf8 = New-Object System.Text.UTF8Encoding($false)
$sourcesFile = Join-Path $run 'sources.txt'
$sources = @(Get-ChildItem -Path src,$generated -Filter '*.java' -Recurse | ForEach-Object { '"' + $_.FullName.Replace('\','/') + '"' })
[IO.File]::WriteAllLines($sourcesFile,$sources,$utf8)
& $javac -encoding UTF-8 -source 8 -target 8 -bootclasspath "$(Join-Path $BuildTools 'core-lambda-stubs.jar');$AndroidJar" -d $classes "@$sourcesFile"
if ($LASTEXITCODE -ne 0) { throw 'Android Java compilation failed.' }
$classJar = Join-Path $run 'classes.jar'
& $jar cf $classJar -C $classes .
if ($LASTEXITCODE -ne 0) { throw 'Class archive creation failed.' }
& $java -cp (Join-Path $BuildTools 'lib\d8.jar') com.android.tools.r8.D8 --lib $AndroidJar --min-api 26 --output $dex $classJar
if ($LASTEXITCODE -ne 0) { throw 'DEX conversion failed.' }
& $jar uf $base -C $dex classes.dex
if ($LASTEXITCODE -ne 0) { throw 'APK assembly failed.' }
$aligned = Join-Path $run 'aligned.apk'
& $align -f -p 4 $base $aligned
if ($LASTEXITCODE -ne 0) { throw 'APK alignment failed.' }
$signing = Join-Path $PSScriptRoot 'signing'
New-Item -ItemType Directory -Path $signing -Force | Out-Null
$keystore = Join-Path $signing 'twisttype-release.jks'
$passwordFile = Join-Path $signing 'password.txt'
if (!(Test-Path -LiteralPath $keystore)) {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes); $rng.Dispose()
    [IO.File]::WriteAllText($passwordFile,[Convert]::ToBase64String($bytes),$utf8)
    & $keytool -genkeypair -keystore $keystore -alias twisttype -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=TwistType Personal' -storepass:file $passwordFile -keypass:file $passwordFile
    if ($LASTEXITCODE -ne 0) { throw 'Signing-key creation failed.' }
}
$release = Join-Path (Split-Path -Parent $PSScriptRoot) 'release\Android'
New-Item -ItemType Directory -Path $release -Force | Out-Null
$apk = Join-Path $release 'TwistType-Android-1.0.2.apk'
& $java -jar (Join-Path $BuildTools 'lib\apksigner.jar') sign --ks $keystore --ks-key-alias twisttype --ks-pass "file:$passwordFile" --v4-signing-enabled false --out $apk $aligned
if ($LASTEXITCODE -ne 0) { throw 'APK signing failed.' }
& $java -jar (Join-Path $BuildTools 'lib\apksigner.jar') verify --verbose $apk
if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed.' }
& (Join-Path $BuildTools 'aapt.exe') dump badging $apk
if ($LASTEXITCODE -ne 0) { throw 'APK manifest inspection failed.' }
Copy-Item -LiteralPath README.md -Destination (Join-Path $release 'INSTALL.txt') -Force
Write-Host "Ready: $apk"
