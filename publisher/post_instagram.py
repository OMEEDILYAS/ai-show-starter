# publisher/post_instagram.py
import os, sys, time, requests

GRAPH = "https://graph.facebook.com/v19.0"

def die(msg, code=2):
    print(msg)
    sys.exit(code)

def preflight(url: str, max_wait=60):
    """Wait until IG can fetch the mp4 URL (HEAD returns 200 and video content)."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            ct = r.headers.get("content-type","")
            print(f"[preflight:HEAD] {r.status_code} {ct} {r.headers.get('content-length','')}")
            if r.status_code == 200 and "video" in ct:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False

def wait_until_ready(creation_id: str, token: str, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{GRAPH}/{creation_id}", params={"fields":"status_code","access_token":token}, timeout=20)
        js = r.json()
        if "status_code" in js and js["status_code"] == "FINISHED":
            print("[poll] ready:", js)
            return True
        if "error" in js:
            print("[poll]", js)
        else:
            print("[poll] processing:", js)
        time.sleep(3)
    print("[poll] timeout waiting for FINISHED")
    return False

def main():
    if len(sys.argv) < 3:
        die("usage: post_instagram.py <video_url> <caption>")

    url = sys.argv[1]
    caption = sys.argv[2]

    token = os.getenv("IG_ACCESS_TOKEN")
    ig_user = os.getenv("IG_USER_ID")
    if not token or not ig_user:
        die("[config] IG_ACCESS_TOKEN and IG_USER_ID are required")

    print("[info] media_url:", url)
    print("[info] caption:", caption)

    if not preflight(url, max_wait=90):
        die("[preflight] URL not yet fetchable by IG; aborting.")

    # whoami (optional)
    try:
        me = requests.get(f"{GRAPH}/me", params={"access_token": token}, timeout=30).json()
        print("[whoami]", {k: me.get(k) for k in ("name","id") if k in me})
    except Exception:
        pass

    # 1) create container
    payload = {
        "media_type": "REELS",   # optional but harmless; IG can infer from video_url
        "video_url": url,
        "caption": caption,
        "access_token": token,
    }
    resp = requests.post(f"{GRAPH}/{ig_user}/media", data=payload, timeout=60).json()
    print("[resp:create]", resp)
    creation_id = resp.get("id")
    if not creation_id:
        die("[create] failed: " + str(resp))

    # 2) poll until FINISHED
    if not wait_until_ready(creation_id, token, timeout=240):
        die("container not ready; aborting.", code=3)

    # 3) publish
    pub = requests.post(f"{GRAPH}/{ig_user}/media_publish",
                        data={"creation_id": creation_id, "access_token": token},
                        timeout=60).json()
    print("[resp:publish]", pub)
    if "id" not in pub:
        die("[publish] failed: " + str(pub))

    print("[ok] posted:", pub["id"])

if __name__ == "__main__":
    main()
