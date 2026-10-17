#!/bin/bash
# Stage 2: wait for the main render, render l3 + textured s6 cuts, convert all to JPEG, sync down, stop the box.
cd ~/Projects/6g-isac; source aws.env; export AWS_PROFILE=enterprises AWS_REGION=us-east-1
K="-i $HOME/.ssh/id_ed25519_aws_devbox -o IdentitiesOnly=yes -o ConnectTimeout=10"
trap 'aws ec2 stop-instances --instance-ids $ID >/dev/null 2>&1' ERR
until timeout 25 ssh $K ubuntu@$IP 'grep -q "^TOTAL" ~/movie/render.log' 2>/dev/null; do sleep 20; done
scp -q $K movie/world.py movie/render.py movie/durations.json movie/tojpg.py ubuntu@$IP:~/movie/
ssh $K ubuntu@$IP 'cd ~/movie && rm -rf frames/s6c1 frames/s6c2 frames/s6c3 && ~/blender/blender-4.5.14-linux-x64/blender -b --python render.py -- ~/movie/frames 1920 804 16 --only l3c1,l3c2,l3c3,s6c1,s6c2,s6c3 > render2.log 2>&1; grep -E "^CUT|^TOTAL|Error" render2.log | tail -8'
ssh $K ubuntu@$IP 'cd ~/movie && . ~/isac/bin/activate && python tojpg.py s1c1 s1c2 s1c3 s2c1 s2c2 s2c3 s6c1 s6c2 s6c3 s7c1 s7c2 s7c3 s9c1 s9c2 s9c3 s10c1 s10c2 l3c1 l3c2 l3c3 | tail -1'
mkdir -p movie/frames
rsync -az --include='*/' --include='*.jpg' --include='anchors.json' --exclude='*' -e "ssh $K" ubuntu@$IP:~/movie/frames/ movie/frames/
aws ec2 stop-instances --instance-ids $ID >/dev/null
echo STAGE2_DONE
