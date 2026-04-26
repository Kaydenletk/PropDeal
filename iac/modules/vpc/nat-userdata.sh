#!/bin/bash
# NAT instance bootstrap — enable IPv4 forwarding + masquerade VPC traffic.
set -eux

sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-nat.conf

iptables -t nat -A POSTROUTING -o eth0 -s 10.0.0.0/16 -j MASQUERADE

# Persist iptables across reboots
yum install -y iptables-services
service iptables save
systemctl enable iptables
systemctl start iptables
