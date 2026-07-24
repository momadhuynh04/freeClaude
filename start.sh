#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "========================================="
echo "   freeClaude - Universal Proxy Server"
echo "========================================="
echo ""

if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED}[!] Khong tim thay moi truong ao venv!${NC}"
    echo -e "${RED}[!] Vui long chay: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

echo -e "${CYAN}[*] Kich hoat moi truong ao Python (venv)...${NC}"
source venv/bin/activate

cleanup() {
    echo ""
    echo -e "${CYAN}[*] Dang tat freeClaude...${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${CYAN}[*] Khoi dong Proxy Server (FastAPI)...${NC}"
python -m cli.main &
BACKEND_PID=$!

sleep 2

echo -e "${CYAN}[*] Mo trinh duyet WebUI...${NC}"
if command -v xdg-open &>/dev/null; then
    xdg-open http://127.0.0.1:8082 &>/dev/null
elif command -v open &>/dev/null; then
    open http://127.0.0.1:8082 &>/dev/null
else
    echo -e "${CYAN}[*] Vui long mo http://127.0.0.1:8082 tren trinh duyet.${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}[OK] freeClaude da duoc chay thanh cong!${NC}"
echo "========================================="
echo "- Nhan Ctrl+C de tat server."
echo ""

wait $BACKEND_PID
