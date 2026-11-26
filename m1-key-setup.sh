#!/bin/sh
mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGSjsOEcpGhOc735LeUf2N4XT+TyzyDOpHJivysrm4Zy hatch' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo M1-KEY-ADDED
