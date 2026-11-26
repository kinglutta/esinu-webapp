$ErrorActionPreference = "Stop"

$tokenPath = Join-Path $env:USERPROFILE "Desktop\esinu-github-token.txt"
if (-not (Test-Path $tokenPath)) {
    throw "Token file not found: $tokenPath"
}

$token = (Get-Content $tokenPath -Raw).Trim()
if (-not $token) {
    throw "Token file is empty: $tokenPath"
}

$gh = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $gh)) {
    throw "GitHub CLI not found at $gh"
}

"Authenticating with token from $tokenPath"
$token | & $gh auth login --with-token

"Creating and pushing public repo esinu-webapp"
& $gh repo create esinu-webapp --public --source=. --remote=origin --push

"Done."
