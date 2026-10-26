#!/usr/bin/env python3
"""Расшифровка с таймингами слов: transcribe.py part1.MOV [part2.MOV ...] -> part1.json ...
Формат: [{start,end,text,words:[{w,s,e}]}]. Модель: env WHISPER_MODEL (по умолчанию small, int8, CPU)."""
import json, os, sys
from faster_whisper import WhisperModel

m = WhisperModel(os.environ.get('WHISPER_MODEL', 'small'), device='cpu', compute_type='int8')
for path in sys.argv[1:]:
    segs, _ = m.transcribe(path, language=os.environ.get('WHISPER_LANG', 'ru'), word_timestamps=True, vad_filter=True)
    out = [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip(),
            'words': [{'w': w.word, 's': round(w.start, 2), 'e': round(w.end, 2)} for w in s.words]} for s in segs]
    dst = os.path.splitext(path)[0] + '.json'
    json.dump(out, open(dst, 'w'), ensure_ascii=False, indent=1)
    print(dst, len(out), 'segments')
