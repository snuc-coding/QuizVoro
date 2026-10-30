$ErrorActionPreference = "Stop"

# Run from quiz-backend with the API server already running. Each stage gets a
# new game in the lobby because the load test starts that game at the end.
$base = if ($env:QUIZVORO_URL) { $env:QUIZVORO_URL.TrimEnd('/') } else { "http://127.0.0.1:8000" }
$stageCounts = @(10, 100, 500, 1000, 1500, 2000)
$rampRate = 3
$connectTimeout = 30

$username = Read-Host "admin"
$securePassword = Read-Host "password" -AsSecureString
$password = [Net.NetworkCredential]::new("", $securePassword).Password

$loginBody = @{ username = $username; password = $password } | ConvertTo-Json -Compress
$login = Invoke-RestMethod -Method Post -Uri "$base/api/v1/admin/login" -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$quizBody = @{ title = "Load Test $(Get-Date -Format yyyyMMdd-HHmmss)"; description = "Local WebSocket load test" } | ConvertTo-Json -Compress
$quiz = Invoke-RestMethod -Method Post -Uri "$base/api/v1/quizzes" -Headers $headers -ContentType "application/json" -Body $quizBody

$roundBody = @{ title = "Round 1"; round_number = 1 } | ConvertTo-Json -Compress
$round = Invoke-RestMethod -Method Post -Uri "$base/api/v1/quizzes/$($quiz.id)/rounds" -Headers $headers -ContentType "application/json" -Body $roundBody

$questionBody = @{
    question_text = "What is 2 + 2?"
    time_limit = 30
    points = 1000
    question_order = 1
    options = @(
        @{ option_text = "3"; is_correct = $false }
        @{ option_text = "4"; is_correct = $true }
    )
} | ConvertTo-Json -Depth 5 -Compress
$question = Invoke-RestMethod -Method Post -Uri "$base/api/v1/rounds/$($round.id)/questions" -Headers $headers -ContentType "application/json" -Body $questionBody

Write-Host "Created quiz $($quiz.id), round $($round.id), question $($question.id)."

foreach ($count in $stageCounts) {
    $gameBody = @{ quiz_id = $quiz.id } | ConvertTo-Json -Compress
    $game = Invoke-RestMethod -Method Post -Uri "$base/api/v1/games" -Headers $headers -ContentType "application/json" -Body $gameBody

    $env:QUIZVORO_ADMIN_USERNAME = $username
    $env:QUIZVORO_ADMIN_PASSWORD = $password
    $env:QUIZVORO_GAME_PIN = $game.pin

    Write-Host "Testing $count clients on fresh game $($game.id) (ramp $rampRate/sec, timeout ${connectTimeout}s)..."
    & python load_tests/websocket_load_test.py `
        --base-url $base `
        --game-id $game.id `
        --clients $count `
        --ramp-rate $rampRate `
        --connect-timeout $connectTimeout `
        --output "load_tests/results-$count.json"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Stage $count did not pass. Stopping here. Game ID: $($game.id)"
        break
    }

    Write-Host "Stage $count passed. Results: load_tests/results-$count.json"
}
