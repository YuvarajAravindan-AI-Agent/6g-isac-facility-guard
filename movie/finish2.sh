#!/bin/bash
cd ~/Projects/6g-isac/movie; . .venv/bin/activate
until grep -q "dash l7" dash2.log; do sleep 10; done
python build.py clip q_seq q_flow q_cfg q_gov s4 s5 > d1.log 2>&1 &
python build.py clip q_audit q_cfar q_repo l6 l7 s1 s10 > d2.log 2>&1 &
python build.py clip s2 s9 s6 s7 l3 > d3.log 2>&1 &
wait
cat d1.log d2.log d3.log
python build.py assemble judge && python build.py assemble long
echo FINISH2_DONE
