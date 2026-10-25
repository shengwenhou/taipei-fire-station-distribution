"""Build the GitHub Pages site (docs/) from web/index.html + web/data.js.

web/index.html is a body fragment (title + style + markup + scripts); this wraps it
in a full HTML document with the same base reset the page was designed against.
"""
import os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, OUT = f"{ROOT}/web", f"{ROOT}/docs"

HEAD = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="臺北市 46 個消防分隊裁撤試算：點選分隊切換保留或裁撤，即時看 10 分鐘覆蓋、平均行車時間與轄區接手情形。">
<style>
:root { color-scheme: light; padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
body { margin: 0; font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
"""

page = open(f"{SRC}/index.html", encoding="utf-8").read()
# keep <title>, font links and the page <style> in <head>; everything from the first <div> on is body
split = page.index('<div class="wrap">')
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
    f.write(HEAD + page[:split].replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
            + "</head>\n<body>\n" + page[split:] + "\n</body>\n</html>\n")
shutil.copy(f"{SRC}/data.js", f"{OUT}/data.js")
open(f"{OUT}/.nojekyll", "w").close()
print("built", OUT, os.listdir(OUT))
