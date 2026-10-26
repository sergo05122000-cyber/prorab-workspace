#!/usr/bin/env python3
"""Приёмка ролика перед отправкой (по образцу qc.py BASEMIND, 24.10). Ноль ошибок — можно сдавать.
  qc.py final.mp4 [1080x1920] [--fix]
Проверяет: разрешение, есть звук, длина видео и звука совпадают (±0,2 с), громкость −14 ±0,5 LUFS,
true peak ≤ −1,0 dBTP, нет чёрных кусков дольше 0,5 с (кроме затемнения в последние 1,5 с).
--fix: если не прошла только громкость/пик — пересобрать звук (усиление + лимитер −1,5 dBTP, до 3 итераций),
видео копируется без перекодирования; файл заменяется, потом повторная проверка."""
import os, re, subprocess, sys, shutil
args = [a for a in sys.argv[1:] if not a.startswith('--')]
F = args[0]; WANT = args[1] if len(args) > 1 else '1080x1920'; FIX = '--fix' in sys.argv

def probe(*a, f=None):
    return subprocess.run(['ffprobe', '-v', 'error', *a, f or F], capture_output=True, text=True).stdout.strip()
def loud(f):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    s = out[out.rfind('Summary:'):]
    return float(re.search(r'I:\s+(-?[\d.]+) LUFS', s).group(1)), float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', s).group(1))

def check():
    errs, loud_errs = [], []
    def ok(cond, good, bad, lo=False):
        print(('ok   ' + good) if cond else ('ERR  ' + bad))
        if not cond: (loud_errs if lo else errs).append(bad)
    res = probe('-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0')
    ok(res == WANT, f'разрешение {res}', f'разрешение {res}, нужно {WANT}')
    has_a = 'audio' in probe('-show_entries', 'stream=codec_type', '-of', 'csv=p=0')
    ok(has_a, 'есть звук', 'нет звуковой дорожки: немой ролик не сдаём')
    dur = float(probe('-show_entries', 'format=duration', '-of', 'csv=p=0') or 0)
    if has_a:
        dv = float(probe('-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0') or 0)
        da = float(probe('-select_streams', 'a:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0') or 0)
        ok(abs(dv - da) <= 0.2, f'длина видео {dv:.2f} / звук {da:.2f}', f'видео {dv:.2f} и звук {da:.2f} расходятся')
        I, pk = loud(F)
        ok(abs(I + 14) <= 0.5, f'громкость {I} LUFS', f'громкость {I} LUFS, нужно −14 ±0,5', lo=True)
        ok(pk <= -1.0, f'пик {pk} dBTP', f'пик {pk} dBTP выше −1', lo=True)
    bd = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', F, '-vf', 'blackdetect=d=0.5:pix_th=0.06', '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    blacks = [(float(a), float(b)) for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', bd) if float(a) < dur - 1.5]
    ok(not blacks, 'чёрных кусков нет', 'чёрные куски: ' + ', '.join(f'{a:.1f}–{b:.1f} с' for a, b in blacks))
    print(f'длительность {dur:.2f} с')
    return errs, loud_errs

def fix_loud():
    tmp = F + '.qcfix.mp4'
    for it in range(3):
        I, pk = loud(F); g = -14 - I
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', F, '-c:v', 'copy', '-af', f'volume={g:.2f}dB,alimiter=limit=0.83:level=false,aresample=48000',
                        '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', tmp], check=True)
        shutil.move(tmp, F); I2, pk2 = loud(F); print(f'  fix {it + 1}: {I} → {I2} LUFS, пик {pk2}')
        if abs(I2 + 14) <= 0.3 and pk2 <= -1.0: break

errs, le = check()
if FIX and le and not errs:
    print('-- чиню громкость'); fix_loud(); errs, le = check()
allerr = errs + le
print('ПРИЁМКА ПРОЙДЕНА' if not allerr else f'ОШИБОК: {len(allerr)} — не отправлять')
sys.exit(1 if allerr else 0)
