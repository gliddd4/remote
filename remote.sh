#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.remote"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
REPO="https://raw.githubusercontent.com/gliddd4/remote/main"

BOLD='\033[1m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}Installing remote...${NC}"

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

echo "  downloading ai_remote.py..."
curl -fsSL "$REPO/macOS/ai_remote.py" -o "$INSTALL_DIR/ai_remote.py"

echo "  downloading requirements..."
curl -fsSL "$REPO/macOS/requirements.txt" -o "$INSTALL_DIR/requirements.txt"

echo "  downloading config..."
curl -fsSL "$REPO/macOS/buttons.json" -o "$INSTALL_DIR/buttons.json"

cat > "$INSTALL_DIR/remote" << 'EOF'
#!/usr/bin/env bash
printf '\033c'
cd "$(dirname "$(readlink -f "$0")")" && exec python3 ai_remote.py
EOF

chmod +x "$INSTALL_DIR/remote"

pip3 install --break-system-packages --user -r "$INSTALL_DIR/requirements.txt" 2>/dev/null || true

[ -L "$BIN_DIR/remote" ] && rm "$BIN_DIR/remote"
ln -s "$INSTALL_DIR/remote" "$BIN_DIR/remote"

hash -r 2>/dev/null || true
echo -e "${GREEN}Done! Run 'remote' to start.${NC}"
