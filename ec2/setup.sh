#!/bin/bash
set -e

fresh_setup() {
    echo ""
    echo "=== Fresh Setup ==="

    echo ""
    echo "[1/4] Installing common tools..."
    sudo apt-get update -q
    sudo apt-get install -y -q git vim htop curl unzip
    echo "Done."

    echo ""
    echo "[2/4] Installing Miniconda..."
    if [ -d "$HOME/miniconda3" ]; then
        echo "Miniconda already installed, skipping."
    else
        curl -sO https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
        bash Miniconda3-latest-Linux-x86_64.sh -b -p "$HOME/miniconda3"
        rm Miniconda3-latest-Linux-x86_64.sh
        "$HOME/miniconda3/bin/conda" init
        echo "Done. Run 'source ~/.bashrc' after this script finishes."
    fi

    echo ""
    echo "[3/4] Creating ~/repos..."
    mkdir -p "$HOME/repos"
    echo "Done."

    echo ""
    echo "[4/4] Setting up GitHub SSH key..."
    if [ -f "$HOME/.ssh/github_key" ]; then
        echo "GitHub key already exists, skipping generation."
    else
        read -p "Enter a label for this key (e.g. your name or this server): " key_label
        ssh-keygen -t ed25519 -C "$key_label" -f "$HOME/.ssh/github_key" -N "" -q

        if ! grep -q "github_key" "$HOME/.ssh/config" 2>/dev/null; then
            cat >> "$HOME/.ssh/config" << 'EOF'

Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_key
EOF
        fi
    fi

    echo ""
    echo "=== Add this key to your GitHub account ==="
    cat "$HOME/.ssh/github_key.pub"
    echo ""
    echo "Steps:"
    echo "  1. Copy the key above"
    echo "  2. Go to GitHub -> Settings -> SSH and GPG keys -> New SSH key"
    echo "  3. Paste and save"
    echo ""
    echo "Then test with: ssh -T git@github.com"
    echo "==========================================="
    echo ""
    echo "=== Setup Complete! ==="
    echo "Run 'source ~/.bashrc' to activate conda."
}

health_check() {
    echo ""
    echo "=== Health Check ==="
    all_ok=true

    echo ""
    echo "[1/3] Checking conda..."
    if [ -d "$HOME/miniconda3" ]; then
        echo "OK — $("$HOME/miniconda3/bin/conda" --version)"
    else
        echo "MISSING — conda not found. Run fresh setup."
        all_ok=false
    fi

    echo ""
    echo "[2/3] Checking GitHub SSH..."
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo "OK — GitHub SSH is working."
    else
        echo "FAILED — GitHub SSH not working. Check your key at GitHub -> Settings -> SSH keys."
        all_ok=false
    fi

    echo ""
    echo "[3/3] Disk space:"
    df -h / | tail -1 | awk '{print "  Used: "$3" / "$2" ("$5" full)"}'

    echo ""
    if [ "$all_ok" = true ]; then
        echo "=== All checks passed! ==="
    else
        echo "=== Some checks failed. See above. ==="
    fi
}

echo "=== EC2 Setup Script ==="
echo ""
echo "Select mode:"
echo "  1. Fresh setup (new EC2)"
echo "  2. Health check (restarted EC2)"
echo ""
read -p "Enter number: " mode

if [ "$mode" = "1" ]; then
    fresh_setup
elif [ "$mode" = "2" ]; then
    health_check
else
    echo "Invalid choice."
    exit 1
fi
