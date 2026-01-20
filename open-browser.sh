#!/bin/bash
# open-browser.sh
# Automatically detect and open browser

NAMESPACE="k8s-multi-demo"

echo "🌐 Opening Kubernetes Demo in Browser"
echo "======================================"
echo ""

# Start port-forward in background
echo "Starting port-forward..."
kubectl port-forward svc/k8s-demo-service 8080:80 -n ${NAMESPACE} > /dev/null 2>&1 &
PF_PID=$!
echo "✅ Port-forward running (PID: $PF_PID)"
sleep 3

URL="http://localhost:8080"

echo ""
echo "Opening: $URL"
echo ""

# Try to find and open browser
if command -v google-chrome &> /dev/null; then
    echo "✅ Opening Google Chrome..."
    google-chrome "$URL" &
elif command -v chromium-browser &> /dev/null; then
    echo "✅ Opening Chromium..."
    chromium-browser "$URL" &
elif command -v chromium &> /dev/null; then
    echo "✅ Opening Chromium..."
    chromium "$URL" &
elif command -v microsoft-edge &> /dev/null; then
    echo "✅ Opening Microsoft Edge..."
    microsoft-edge "$URL" &
elif command -v opera &> /dev/null; then
    echo "✅ Opening Opera..."
    opera "$URL" &
elif command -v brave-browser &> /dev/null; then
    echo "✅ Opening Brave..."
    brave-browser "$URL" &
elif command -v firefox &> /dev/null; then
    echo "✅ Opening Firefox..."
    firefox "$URL" &
elif command -v xdg-open &> /dev/null; then
    echo "✅ Opening default browser..."
    xdg-open "$URL" &
else
    echo "⚠️  No graphical browser found!"
    echo ""
    echo "Manual options:"
    echo "1. Install a browser:"
    echo "   sudo apt install chromium-browser"
    echo ""
    echo "2. Use text browser:"
    echo "   sudo apt install lynx"
    echo "   lynx $URL"
    echo ""
    echo "3. Test with curl:"
    echo "   curl $URL"
    echo ""
    echo "4. Copy this URL and paste in any browser:"
    echo "   $URL"
fi

echo ""
echo "📝 Port-forward is running in background"
echo "   PID: $PF_PID"
echo "   To stop: kill $PF_PID"
echo ""
echo "🌐 URL: $URL"
