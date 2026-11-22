"""Assemble the single-page app from template.html, data.json and icons/. Run from the app folder."""
import re, json, glob, os
ic = {}
for f in glob.glob("icons/*.svg"):
    s = open(f).read(); s = re.sub(r'\s(width|height)="48"', "", s, count=2); ic[os.path.basename(f)[:-4]] = re.sub(r"\s+", " ", s).strip()
t = open("template.html").read(); d = open("data.json").read()
assert t.count("/*__DATA__*/null") == 1 and t.count("/*__ICONS__*/{}") == 1
frag = t.replace("/*__ICONS__*/{}", json.dumps(ic).replace("</", "<\\/")).replace("/*__DATA__*/null", d)
open("sahi-ilaj.html", "w").write(frag)
open("index.html", "w").write('<!doctype html>\n<html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0">\n' + frag + "\n</body></html>")
open("check.js", "w").write("\n".join(re.findall(r"<script>(.*?)</script>", frag, re.S)))
print("built", len(frag.encode()), "bytes")
