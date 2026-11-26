#!/usr/bin/env python3
"""Build q/<name>.js from tools/qsrc/<module>.py.
Usage: python3 tools/build_questions.py s1_batch1 s1-batch1
Source rows: (system, discipline, stem, correct, [4 distractors], explanation, "F"|"C")
Output rows: [system, stem, options, answerIndex, explanation, 1 (= new, unchecked), level, discipline]
Answer positions are shuffled with a fixed seed so rebuilds are stable.
Question files are APPEND-ONLY: progress is stored by question index, so never
reorder, remove or insert questions in an existing file, and always add new
files at the END of the script list in index.html. To fix a question, edit it in place.
"""
import sys, json, random, importlib, os, hashlib, re, glob
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools", "qsrc"))
SYSTEMS = ["Human development", "Blood & immune", "Nervous system & behavior", "Musculoskeletal & skin",
           "Cardiovascular", "Respiratory & renal", "Gastrointestinal", "Reproductive & endocrine",
           "Multisystem", "Biostatistics & epidemiology", "Communication & ethics"]
mod, out = sys.argv[1], sys.argv[2]
src = importlib.import_module(mod).Q
rows = []
for system, disc, stem, right, wrong, exp, level in src:
    assert system in SYSTEMS, system
    assert len(wrong) == 4, stem
    assert right not in wrong, stem
    opts = [right] + list(wrong)
    rnd = random.Random(hashlib.md5(stem.encode()).hexdigest())
    rnd.shuffle(opts)
    rows.append([system, stem, opts, opts.index(right), exp, 1, level, disc])
stems = [r[1] for r in rows]
assert len(stems) == len(set(stems)), "duplicate stem"
others = set()
for f in glob.glob(os.path.join(root, "q", "*.js")):
    if f.endswith(out + ".js"): continue
    others |= {m.lower() for m in re.findall(r'\["[^"]*", ?"((?:[^"\\]|\\.)*)"', open(f).read())}
dup = [x for x in stems if x.lower() in others]
assert not dup, "stem already in bank: %r" % dup
body = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
open(os.path.join(root, "q", out + ".js"), "w").write("// Built from tools/qsrc/%s.py. Append-only.\nQ.push(\n%s\n);\n" % (mod, body))
print(out, len(rows), "questions; answer positions:", [sum(1 for r in rows if r[3] == k) for k in range(5)])
from collections import Counter
print(Counter(r[0] for r in rows))
