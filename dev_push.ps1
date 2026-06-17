# ArchAutoMap 개발용 빠른 Git 커밋 + 푸시 스크립트
# 사용법: .\dev_push.ps1 "커밋 메시지"
# 예시:   .\dev_push.ps1 "fix: 축척 계산 버그 수정"

param(
    [Parameter(Mandatory=$false)]
    [string]$Message = ""
)

Set-Location $PSScriptRoot

# 상태 확인
Write-Host "`n=== Git 상태 ===" -ForegroundColor Cyan
git status --short

# 변경된 파일이 없으면 종료
$changes = git status --porcelain
if (-not $changes) {
    Write-Host "`n변경된 파일이 없습니다." -ForegroundColor Yellow
    exit 0
}

# 커밋 메시지가 없으면 입력 요청
if (-not $Message) {
    Write-Host "`n커밋 메시지를 입력하세요:" -ForegroundColor Green
    $Message = Read-Host
}

if (-not $Message) {
    Write-Host "커밋 메시지가 비어 있습니다. 중단합니다." -ForegroundColor Red
    exit 1
}

# 스테이징 + 커밋 + 푸시
Write-Host "`n=== 스테이징 ===" -ForegroundColor Cyan
git add -A

Write-Host "`n=== 커밋: $Message ===" -ForegroundColor Cyan
git commit -m $Message

Write-Host "`n=== GitHub 푸시 ===" -ForegroundColor Cyan
git push origin HEAD

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ 푸시 완료!" -ForegroundColor Green
    Write-Host "QGIS Python Console에서 다음 명령어로 즉시 리로드하세요:" -ForegroundColor Yellow
    Write-Host "  exec(open(r'C:\Users\nuri9\Documents\archautomap\dev_reload.py').read())" -ForegroundColor White
} else {
    Write-Host "`n❌ 푸시 실패. git 인증/네트워크를 확인하세요." -ForegroundColor Red
}
