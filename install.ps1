$ErrorActionPreference = "Stop"

$NexusHome = Join-Path $HOME ".nexus"
$EnvDir = Join-Path $NexusHome "env"
$SrcDir = Join-Path $NexusHome "src"
$DefaultRepoUrl = "https://github.com/Ezequiel135/Nexus-Agent.git"
$RepoUrl = if ($env:NEXUS_REPO_URL) { $env:NEXUS_REPO_URL } else { $DefaultRepoUrl }
$WrapperBat = Join-Path $NexusHome "nexus.bat"
$ProfileDir = Split-Path -Parent $PROFILE

Write-Host "[1/6] Verificando Python 3.10+"
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"

Write-Host "[2/6] Preparando diretorios do NEXUS AGENT"
New-Item -ItemType Directory -Force -Path $NexusHome | Out-Null

Write-Host "[3/6] Baixando ou copiando o codigo"
if ((Test-Path ".git") -and (Test-Path "main.py")) {
    if (Test-Path $SrcDir) { Remove-Item -Recurse -Force $SrcDir }
    Copy-Item -Recurse -Force (Get-Location) $SrcDir
} else {
    if (Test-Path $SrcDir) { Remove-Item -Recurse -Force $SrcDir }
    git clone $RepoUrl $SrcDir
}
Set-Content -Path (Join-Path $NexusHome "repo.txt") -Value $RepoUrl -Encoding utf8

Write-Host "[4/6] Criando ambiente virtual"
python -m venv $EnvDir

Write-Host "[5/6] Instalando dependencias Python"
& (Join-Path $EnvDir "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $EnvDir "Scripts\python.exe") -m pip install -r (Join-Path $SrcDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] requirements.txt completo falhou. Instalando conjunto minimo..."
    & (Join-Path $EnvDir "Scripts\python.exe") -m pip install rich litellm requests python-dotenv psutil textual nbformat nbclient ipykernel
}

Write-Host "[6/6] Criando launcher do Windows"
$batContent = "@echo off`r`n`"" + (Join-Path $EnvDir "Scripts\python.exe") + "`" `"" + (Join-Path $SrcDir "main.py") + "`" %*`r`n"
Set-Content -Path $WrapperBat -Value $batContent -Encoding ascii

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Force -Path $PROFILE | Out-Null }
$profileText = Get-Content $PROFILE -Raw
if ($profileText -notmatch [regex]::Escape($NexusHome)) {
    Add-Content $PROFILE "`n`$env:Path += ';$NexusHome'"
}

Write-Host "Instalacao do NEXUS AGENT 26.4.4 concluida. Abra um novo terminal e rode: nexus"
Write-Host "Na primeira abertura, escolha a UI (Visual ou Plain) e conclua o setup."
