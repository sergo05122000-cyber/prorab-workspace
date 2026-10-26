#!/usr/bin/env python3
"""Подрезка пауз в говорящей голове + проверка (правило Сергея с 08.10).
Использование: trim_pauses.py in.mp4 [out.mp4]
1) транскрипт whisper (in.json рядом, если нет — создаётся);
2) тишина по silencedetect (−35 dB, ≥0.3 с); режем только тишину:
   ≥0.12 с после последнего слова, ≥0.06–0.08 с до следующего, внутрь слов whisper не заходим;
3) склейка с 12-мс фейдами звука, 30 к/с;
4) проверка: повторная расшифровка результата, совпадение слов ≥0.93, иначе exit 1 и список расхождений."""
import json, re, subprocess, sys, os, difflib
src = sys.argv[1]; base = os.path.splitext(src)[0]
out = sys.argv[2] if len(sys.argv) > 2 else base + '_cut.mp4'
TR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcribe.py')
env = dict(os.environ, WHISPER_MODEL=os.environ.get('WHISPER_MODEL', 'small'))
def tr(path):
    j = os.path.splitext(path)[0] + '.json'
    if not os.path.exists(j): subprocess.run([sys.executable, TR, path], env=env, capture_output=True, check=True)
    return [w for s in json.load(open(j)) for w in s['words']]
words = tr(src)
log = subprocess.run(['ffmpeg', '-hide_banner', '-i', src, '-af', 'silencedetect=noise=-35dB:d=0.3', '-f', 'null', '-'], capture_output=True, text=True).stderr
ss = [float(x) for x in re.findall(r'silence_start: ([0-9.]+)', log)]; ee = [float(x) for x in re.findall(r'silence_end: ([0-9.]+)', log)]
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout)
cuts = []
for s, e in zip(ss, ee):
    a = 0 if s < 0.05 else s + 0.12
    b = e - 0.08
    prev = [w['e'] for w in words if w['e'] <= b and w['s'] < a + 0.3]
    nxt = [w['s'] for w in words if w['s'] >= a - 0.3 and w['e'] > b]
    if prev and s >= 0.05: a = max(a, max(prev) + 0.08)
    if nxt: b = min(b, min(nxt) - 0.06)
    if b - a >= 0.12: cuts.append((a, b))
keep = []; t = 0
for a, b in cuts: keep.append((t, a)); t = b
keep.append((t, dur)); keep = [(round(x, 3), round(y, 3)) for x, y in keep if y - x > 0.05]
parts = []; labels = ''
for i, (a, b) in enumerate(keep):
    d = b - a
    parts.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=30[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={d-0.012:.3f}:d=0.012[a{i}]")
    labels += f"[v{i}][a{i}]"
fc = ';'.join(parts) + f";{labels}concat=n={len(keep)}:v=1:a=1[v][a]"
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', out], check=True)
json.dump(keep, open(os.path.splitext(out)[0] + '_keep.json', 'w'))
n = lambda ws: [re.sub(r'[^\wё]', '', w['w'].lower()) for w in ws]
A = n(words); B = n(tr(out))
sm = difflib.SequenceMatcher(None, A, B); r = sm.ratio()
print(f'removed {sum(b-a for a,b in cuts):.2f}s in {len(cuts)} cuts; words {len(A)}→{len(B)}; match {r:.3f}')
for op in sm.get_opcodes():
    if op[0] != 'equal': print('  ', op[0], A[op[1]:op[2]], '→', B[op[3]:op[4]])
sys.exit(0 if r >= 0.93 else 1)
