#!/bin/bash

# Script name: fix_install.sh
# Description: Removes Windows-style line endings from install.sh in the current directory.

echo "[*] Fixing line endings in install.sh..."
sed -i 's/\r$//' install.sh

if [ $? -eq 0 ]; then
    echo "[+] install.sh cleaned successfully."
else
    echo "[-] Failed to clean install.sh."
    exit 1
fi
