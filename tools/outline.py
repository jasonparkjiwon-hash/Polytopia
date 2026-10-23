"""Print a file's functions and big blocks with line numbers, so you can Read only the part you need.
Usage: python3 -I tools/outline.py engine/replay.py"""
import sys, re
for n, l in enumerate(open(sys.argv[1]), 1):
    if re.match(r"(def |class |[A-Z_]+ = |if __name__)", l) or re.match(r"    (elif|if) t == \d+", l):
        print(n, l.rstrip()[:110])
