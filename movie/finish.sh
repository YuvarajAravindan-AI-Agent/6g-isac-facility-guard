#!/bin/bash
cd ~/Projects/6g-isac/movie; . .venv/bin/activate
python build.py clip s1 s10 > c1.log 2>&1 &
python build.py clip s2 s9 > c2.log 2>&1 &
python build.py clip s6 s7 l3 > c3.log 2>&1 &
wait
cat c1.log c2.log c3.log
python build.py assemble judge && python build.py assemble long
echo FINISH_DONE
