param([Parameter(Mandatory=$true)][string]$OutputDir)

Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Write-Voice([string]$voice, [int]$rate, [string]$text, [string]$path) {
    $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $speaker.SelectVoice($voice)
    $speaker.Rate = $rate
    $speaker.Volume = 92
    $speaker.SetOutputToWaveFile($path)
    $speaker.Speak($text)
    $speaker.Dispose()
}

Write-Voice 'Microsoft David Desktop' 1 "So MyRecon finds every account I've ever made?" (Join-Path $OutputDir 'kabir-1.wav')
Write-Voice 'Microsoft Zira Desktop' 1 "No. If it can't check, it says unknown." (Join-Path $OutputDir 'meera-1.wav')
Write-Voice 'Microsoft David Desktop' 2 "That's actually honest." (Join-Path $OutputDir 'kabir-2.wav')
Write-Voice 'Microsoft Zira Desktop' 0 "Shh." (Join-Path $OutputDir 'meera-2.wav')
