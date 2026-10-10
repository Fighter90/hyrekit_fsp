import glob, os, shutil, subprocess, sys, zipfile
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
d = src + '.x'
shutil.rmtree(d, ignore_errors=True)
zipfile.ZipFile(src).extractall(d)
for p in glob.glob(d + '/ppt/media/*.png'):
    if os.path.getsize(p) < 1_000_000:
        continue
    im = Image.open(p)
    if im.mode == 'RGBA' and im.getchannel('A').getextrema()[0] < 255:
        im.resize((2560, round(2560 * im.height / im.width)), Image.LANCZOS).save(p, optimize=True)
        continue
    f = os.path.basename(p); new = f[:-4] + '.jpg'
    im.convert('RGB').resize((2560, round(2560 * im.height / im.width)), Image.LANCZOS).save(d + '/ppt/media/' + new, quality=88, optimize=True)
    os.remove(p)
    for r in glob.glob(d + '/ppt/**/_rels/*.rels', recursive=True):
        t = open(r).read()
        if 'media/' + f + '"' in t:
            open(r, 'w').write(t.replace('media/' + f + '"', 'media/' + new + '"'))
ct = open(d + '/[Content_Types].xml').read()
if 'Extension="jpg"' not in ct:
    open(d + '/[Content_Types].xml', 'w').write(ct.replace('<Default Extension="xml"', '<Default Extension="jpg" ContentType="image/jpeg"/><Default Extension="xml"'))
if os.path.exists(dst): os.remove(dst)
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(d + '/[Content_Types].xml', '[Content_Types].xml')
    for root, _, files in os.walk(d):
        for fn in files:
            full = os.path.join(root, fn); arc = os.path.relpath(full, d)
            if arc != '[Content_Types].xml': z.write(full, arc)
shutil.rmtree(d)
