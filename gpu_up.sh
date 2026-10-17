#!/bin/bash
# Start the isac-sim box (if needed), refresh SG + aws.env, wait for SSH. Does NOT stop it.
cd ~/Projects/6g-isac; source aws.env; export AWS_PROFILE=enterprises AWS_REGION=us-east-1
K="-i $HOME/.ssh/id_ed25519_aws_devbox -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new"
ST=$(aws ec2 describe-instances --instance-ids $ID --query 'Reservations[0].Instances[0].State.Name' --output text)
[ "$ST" = stopping ] && timeout 280 aws ec2 wait instance-stopped --instance-ids $ID
[ "$ST" != running ] && { aws ec2 start-instances --instance-ids $ID >/dev/null; aws ec2 wait instance-running --instance-ids $ID; }
IP=$(aws ec2 describe-instances --instance-ids $ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
MYIP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 22 --cidr ${MYIP}/32 2>&1 | grep -v Duplicate || true
printf 'ID=%s\nSG=%s\nIP=%s\n' $ID $SG $IP > aws.env
for i in $(seq 1 40); do ssh $K ubuntu@$IP true 2>/dev/null && echo "up $IP" && break; sleep 5; done
