# -*- coding: utf-8 -*-
"""
**아카이브 인덱스 목록 재생성** — 저장소 안에 하나만 두는 정본.

  왜 이게 저장소 안에 있나 (2026-09-13)
  ------------------------------------
  `index.html` 은 **발행할 때마다 통째로 다시 만들어진다.** 그런데 그걸 만드는
  `publish.py` 는 **여러 대에 사본으로 흩어져 있다.**

      이 PC     …/주식유튜버 요약/_tools/publish.py
      서버 PC   C:\\briefing\\_tools\\publish.py   ← 한 번 복사해 간 사본, 동기화 없음

  서버 사본이 `scan` 을 모르는 옛 버전이라, 9/13 아침 미국장 브리핑이 나가면서
  9/12 에 올린 **스캔 목록이 인덱스에서 통째로 사라졌다.** 파일은 남아 있는데
  링크만 없어져 사이트에서 안 보였다.

  → 그래서 **GitHub Actions 가 push 될 때마다 이 스크립트로 목록을 다시 만든다.**
    어느 PC가 어떤 버전으로 무엇을 올리든, 최종 인덱스는 항상 저장소 내용과 일치한다.
    사본이 몇 대에 흩어져 있어도 상관없어진다.

  ── 설계에서 일부러 좁게 잡은 것
  이 스크립트는 **`<div id="list">` 안쪽만 갈아끼운다.** 인덱스 전체를 다시 만들지
  않는다. 그래야 HTML 템플릿과 CSS 를 여기에 복사해 둘 필요가 없다.
  복사해 두면 `publish.py` 쪽에서 디자인을 고쳤을 때 이 스크립트가 **옛 디자인으로
  되돌려 버리는** 더 나쁜 사고가 난다.
  같은 이유로 `assets/site.css` 는 **건드리지 않는다.** 그건 publish.py 소관이다.

      python _site_tools/build_index.py [저장소경로]
"""
from __future__ import annotations

import glob
import html
import os
import re
import sys

# 이름표. 여기 없는 폴더가 나와도 버리지 않고 폴더명을 그대로 쓴다.
LABELS = {"kr": "한국장", "us": "미국장", "stock": "종목", "scan": "스캔"}
ORDER = {"kr": 0, "us": 1, "stock": 2, "scan": 3}
SKIP = {"assets", "_site_tools", "node_modules"}

BEGIN = '<div id="list">'
END = '<p class="empty" id="none"'


def first_heading(path: str) -> str:
    """리포트 HTML 의 첫 제목. 인덱스 카드의 부제로 쓴다."""
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read(20000)
    except OSError:
        return ""
    for pat in (r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"):
        m = re.search(pat, head, re.S | re.I)
        if m:
            t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            # <title> 은 "스캔 2026-09-12 03:22 · 장 마감 후" 처럼 접두어가 붙는다
            return t
    return ""


def markets(repo: str) -> list:
    """저장소에 **실제로 있는** 마켓 폴더. 모르는 폴더도 버리지 않는다."""
    out = []
    for name in sorted(os.listdir(repo)):
        p = os.path.join(repo, name)
        if not os.path.isdir(p) or name.startswith(".") or name in SKIP:
            continue
        if glob.glob(os.path.join(p, "*.html")):
            out.append(name)
    return out


def collect(repo: str) -> dict:
    items = {}
    for m in markets(repo):
        for p in glob.glob(os.path.join(repo, m, "*.html")):
            base = os.path.basename(p)
            if base == "index.html" or base.endswith("-dashboard.html"):
                continue
            date = base[:-5]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                continue
            items.setdefault(date, []).append((m, first_heading(p)))
    return items


def rows_html(items: dict) -> str:
    rows = []
    for date in sorted(items, reverse=True):
        cards = []
        for m, headline in sorted(items[date], key=lambda x: ORDER.get(x[0], 9)):
            label = LABELS.get(m, m)
            key = f"{date} {label} {headline}".lower()
            sub = html.escape(headline) if headline else ""
            cards.append(
                f'      <a class="row" data-k="{html.escape(key)}" '
                f'href="{m}/{date}.html">'
                f'<span class="tag {m}">{label}</span>'
                f'<span class="t">{date} {label} 브리핑<small>{sub}</small></span>'
                f'<span class="go">열기 →</span></a>')
        rows.append(f'    <div class="day">\n      <h2>{date}</h2>\n'
                    + "\n".join(cards) + "\n    </div>")
    if not rows:
        rows = ['    <p class="empty">아직 발행된 리포트가 없습니다.</p>']
    return "\n".join(rows)


def main() -> int:
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    idx = os.path.join(repo, "index.html")
    if not os.path.exists(idx):
        print("index.html 이 없습니다. publish.py 가 한 번은 돌아야 합니다.")
        return 1
    cur = open(idx, encoding="utf-8").read()
    a, b = cur.find(BEGIN), cur.find(END)
    if a < 0 or b < 0 or b <= a:
        # 템플릿이 바뀌어 표지를 못 찾으면 **아무것도 하지 않는다.**
        # 잘못 자르느니 그대로 두는 게 낫다.
        print(f"표지를 못 찾았습니다 ({BEGIN} … {END}). 손대지 않고 끝냅니다.")
        return 1

    items = collect(repo)
    body = rows_html(items)
    # 표지 사이만 갈아끼운다. 앞뒤 여백까지 원본 그대로 맞춰야 한다 —
    # 한 줄이라도 어긋나면 내용이 같아도 매번 봇 커밋이 생긴다.
    new = cur[:a] + BEGIN + "\n" + body + "\n  </div>\n  " + cur[b:]

    if new == cur:
        print("변경 없음")
        return 0
    open(idx, "w", encoding="utf-8").write(new)
    n = sum(len(v) for v in items.values())
    print(f"인덱스 목록 재생성: {len(items)}일 · {n}건 · "
          f"마켓 {', '.join(markets(repo))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
