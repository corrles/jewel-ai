# Quick smoke test for Jewel
# Checks /health and does a cheap video_summary (quick mode) to validate the pipeline.

$base = 'http://127.0.0.1:8000'
Write-Output "Smoke test: checking $base"

try {
    $h = Invoke-RestMethod -Method Get -Uri "$base/health" -ErrorAction Stop
    Write-Output "HEALTH: $($h | ConvertTo-Json -Depth 4)"
} catch {
    Write-Output "ERROR: /health failed: $_"
    exit 2
}

# Cheap sample video: short clip or public video. Use quick:true to reduce load.
$sample = 'https://www.youtube.com/watch?v=ysz5S6PUM-U' # small autoplay demo video (YouTube sample)
$payload = @{ url = $sample; every = 30; max_frames = 1; quick = $true } | ConvertTo-Json
try {
    Write-Output "Posting quick video_summary (cheap) to $base/video_summary"
    $r = Invoke-RestMethod -Method Post -Uri "$base/video_summary" -ContentType 'application/json' -Body $payload -TimeoutSec 300
    if ($r.reply) {
        Write-Output "VIDEO SUMMARY REPLY:"
        Write-Output $r.reply
    } else {
        Write-Output "VIDEO SUMMARY RESULT:"
        Write-Output ($r | ConvertTo-Json -Depth 6)
    }
} catch {
    Write-Output "VIDEO SUMMARY ERROR: $_"
    # If OpenAI returns 429 or other JSON, try to parse
    try {
        $err = $_.Exception.Response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
        Write-Output "Parsed error:"
        Write-Output ($err | ConvertTo-Json -Depth 6)
    } catch { }
    exit 3
}

Write-Output "Smoke test completed successfully."
