# publisher/post_instagram.py
import os, sys, time, json
import requests

GRAPH = "https://graph.facebook.com/v19.0"

def die(msg, code=1):
    print(msg)
    sys.exit(code)

def head_ok_once(url: str):
    try:
        r = requests.head(url, timeout=30, allow_redirects=True)
        ct = (r.headers.get("Content-Type") or "").lower()
        cl_raw = r.headers.get("Content-Length") or "0"
        try:
            cl = int(cl_raw)
        except:
            cl = 0
        print("[preflight:HEAD]", r.status_code, ct, cl)
        # GH Pages sometimes serves octet-stream; accept it.
        ct_ok = ("video" in ct) or ("octet-stream" in ct)
        return r.status_code == 200 and ct_ok and (0 < cl < 100 * 1024 * 1024)
    except Exception as e:
        print("[preflight:HEAD] error:", e)
        return False

def wait_until_fetchable(url: str, timeout_sec=180, sleep_sec=5):
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        if head_ok_once(url):
            return True
        time.sleep(sleep_sec)
    return False

def main():
    token = os.environ.get("IG_ACCESS_TOKEN")
    user_id = os.environ.get("IG_USER_ID")
    media_url = sys.argv[1] if len(sys.argv) >= 2 else os.environ.get("MEDIA_URL")
    caption = sys.argv[2] if len(sys.argv) >= 3 else os.environ.get("CAPTION", "")

    if not token or not user_id:
        die("[config] IG_ACCESS_TOKEN and IG_USER_ID must be set.", 2)
    if not media_url:
        die("[config] MEDIA URL missing (argv[1] or MEDIA_URL).", 2)

    print("[info] media_url:", media_url)
    print("[info] caption:", caption[:80] + ("…" if len(caption) > 80 else ""))

    print("[preflight] waiting for URL to be fetchable by IG…")
    if not wait_until_fetchable(media_url):
        die("[preflight] URL did not become fetchable within timeout; aborting.", 2)

    try:
        me = requests.get(f"{GRAPH}/me", params={"access_token": token}, timeout=60).json()
        print("[whoami]", me)
    except Exception as e:
        die(f"[whoami] request failed: {e}", 3)

    # 1) create upload container
    try:
        create = requests.post(
            f"{GRAPH}/{user_id}/media",
            params={"access_token": token},
            data={"media_type": "REELS", "video_url": media_url, "caption": caption},
            timeout=120,
        ).json()
    except Exception as e:
        die(f"[create] request failed: {e}", 3)

    creation_id = (create or {}).get("id")
    print("[resp:create]", create)
    if not creation_id:
        die("[create] failed to obtain creation_id", 3)

    print("[step] wait until ready…")
    for i in range(30):  # ~150s
        time.sleep(5)
        try:
            poll = requests.get(
                    f"{GRAPH}/{creation_id}",
                    params={"fields": "status_code,error_message,error_code", "access_token": token},
                    timeout=60,
            ).json()
        except Exception as e:
            print(f"[poll {i+1}] request error:", e)
            continue

        print(f"[poll {i+1}]", poll)
        sc = (poll or {}).get("status_code")
        if sc == "FINISHED":
            break
        if sc == "ERROR":
            die(json.dumps(poll, indent=2), 3)
    else:
        die("[poll] timeout waiting for FINISHED", 3)

    # 3) publish
    try:
        pub = requests.post(
            f"{GRAPH}/{user_id}/media_publish",
            params={"access_token": token},
            data={"creation_id": creation_id},
            timeout=120,
        ).json()
    except Exception as e:
        die(f"[publish] request failed: {e}", 3)

    print("[publish]", pub)
    if "id" not in pub:
        die("[publish] failed", 3)

    print("[ok] post_instagram.py finished")

if __name__ == "__main__":
    main()
