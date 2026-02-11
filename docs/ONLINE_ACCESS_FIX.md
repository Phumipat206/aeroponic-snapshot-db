# Online Access — Troubleshooting

## Problem: "Current Share Link" Not Working

This happens when **cloudflared** is not installed or not found.

---

## Solution

### Automatic (Recommended)

Run `bash start.sh` — it automatically downloads cloudflared during setup.

### Manual Download

```bash
# x86_64 (PC/Server)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -O src/cloudflared
chmod +x src/cloudflared

# Raspberry Pi (ARM64)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" -O src/cloudflared
chmod +x src/cloudflared

# Verify
./src/cloudflared --version
```

---

## Using Online Access

### Steps:

1. **Open the Online Access page**
   - Go to `https://localhost:8443/online`

2. **Click "Start Online Access"**
   - The system will create a Cloudflare Tunnel
   - A public URL will appear under "Current Share Link"

3. **Share the URL**
   - Click the Copy icon to copy the URL
   - Send it to anyone who needs access

4. **Stop Online Access**
   - Click **Stop Tunnel** when done

---

## Troubleshooting

### Error: "cloudflared not found"

```bash
# Check if cloudflared exists
ls -la src/cloudflared

# If not found, download it (see Manual Download above)
```

### Error: "Timeout waiting for tunnel URL"

1. Wait a moment — first start may be slow
2. Temporarily check firewall settings
3. Try clicking **Start Online Access** again

### Error: "Permission denied"

```bash
chmod +x src/cloudflared
```

---

## Status Indicators

On the Online Access page:
- **Active** = Tunnel is running, URL is available
- **Not Set** = Tunnel has not been started

In the terminal:
```
Tunnel started successfully
URL: https://xxxx-xxxx-xxxx.trycloudflare.com
```

---

## Security Reminder

After use, click **Stop Tunnel** to:
- Close public access to your server
- Save bandwidth
- Improve security
