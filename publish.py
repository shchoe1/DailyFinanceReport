"""리포트 HTML을 GitHub Pages에 게시 → 카톡 '자세히 보기'가 열 공개 URL 반환.
설정(.env): GITHUB_USER, GITHUB_REPO(공개), GITHUB_TOKEN(PAT, contents 쓰기).
미설정/실패 시 None 반환하고 발송은 링크 없이 계속된다.

동작: 로컬 site/ 를 대상 저장소의 로컬 git 작업본으로 사용하여
      매일 report_YYYY-MM-DD.html + index.html(오늘로 리다이렉트)를 커밋·푸시.
공개 URL: https://<USER>.github.io/<REPO>/report_YYYY-MM-DD.html
"""
from __future__ import annotations
import shutil
import subprocess
from config import (SITE_DIR, GITHUB_USER, GITHUB_REPO, GITHUB_TOKEN, GITHUB_BRANCH,
                    REPORT_BASE_URL)


def _git(args: list[str]):
    return subprocess.run(["git", *args], cwd=str(SITE_DIR),
                          capture_output=True, text=True, timeout=120)


def _remote_url() -> str:
    return f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"


def _ensure_repo() -> None:
    SITE_DIR.mkdir(exist_ok=True)
    if not (SITE_DIR / ".git").exists():
        _git(["init"])
        _git(["checkout", "-B", GITHUB_BRANCH])
        _git(["remote", "add", "origin", _remote_url()])
    else:
        _git(["remote", "set-url", "origin", _remote_url()])
    _git(["config", "user.email", f"{GITHUB_USER}@users.noreply.github.com"])
    _git(["config", "user.name", GITHUB_USER])


def _index_html(today: str) -> str:
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta http-equiv='refresh' content='0; url=report_{today}.html'>"
            f"<title>한국증시 수급 브리핑</title></head>"
            f"<body>오늘 리포트로 이동 중… "
            f"<a href='report_{today}.html'>report_{today}.html</a></body></html>")


def _write_site(html_path: str, today: str) -> None:
    SITE_DIR.mkdir(exist_ok=True)
    shutil.copy(html_path, SITE_DIR / f"report_{today}.html")
    (SITE_DIR / "index.html").write_text(_index_html(today), encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")  # Jekyll 처리 방지


def publish_report(html_path: str, today: str) -> str | None:
    # 1) 클라우드(GitHub Actions): site/ 만 생성 → Pages 배포는 워크플로가 처리
    if REPORT_BASE_URL:
        _write_site(html_path, today)
        return f"{REPORT_BASE_URL}/report_{today}.html"

    # 2) 로컬: PAT 로 GitHub 저장소에 직접 push
    if not (GITHUB_USER and GITHUB_REPO and GITHUB_TOKEN):
        return None
    if not shutil.which("git"):
        return None
    try:
        _ensure_repo()
        _write_site(html_path, today)
        _git(["add", "-A"])
        _git(["commit", "-m", f"report {today}"])   # 변경 없으면 실패해도 무시
        push = _git(["push", "-u", "origin", GITHUB_BRANCH])
        if push.returncode != 0:
            print("[github] push 실패:", (push.stderr or push.stdout)[-400:])
            return None
        return f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/report_{today}.html"
    except Exception as e:
        print("[github] 오류:", e)
        return None


if __name__ == "__main__":
    import sys
    import datetime as dt
    from config import REPORTS_DIR
    today = dt.date.today().strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"report_{today}.html"
    if not path.exists():
        print("리포트가 없습니다. 먼저 main.py --dry-run 실행:", path)
        sys.exit(1)
    print("게시 URL:", publish_report(str(path), today) or "(설정 없음/실패)")
