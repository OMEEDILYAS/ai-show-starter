# publisher/post_instagram.py
import os, sys, time, json
import requests

GRAPH = "https://graph.facebook.com/v19.0"

def env_required(key: str) -> str:
    v = os.environ.get(key, "").strip()
    if not v:
        print(f"[ERROR] missing env: {key}", file=sys.stderr)
        sys.exit(2)
    return v

def die(msg: str, data=None, code=1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    if data is not None:
        try:
            print(json.dumps(data, indent=2))
        except Exception:
            print(str(data))
    sys.exit(code)

def main():
    if len(sys.argv) != 3:
        print("usage: post_instagram.py <video_url_or_path> <caption>", file=sys.stderr)
        sys.exit(2)
    src, caption = sys.argv[1], sys.argv[2]

    token = env_required("IG_ACCESS_TOKEN")
    ig_user = env_required("IG_USER_ID")

    # sanity: who am I?
    me = requests.get(f"{GRAPH}/me", params={"access_token": token}, timeout=30).json()
    print("[whoami]", me)

    # Create container (by URL or file)
    params = {
        "caption": caption,
        "media_type": "REELS",
        "share_to_feed": "true",
        "access_token": token,
    }
    files = None
    if src.startswith("http://") or src.startswith("https://"):
        params["video_url"] = src
    else:
        if not os.path.isfile(src):
            die(f"file not found: {src}")
        files = {"video_file": open(src, "rb")}

    print("[step] create container…")
    r = requests.post(f"{GRAPH}/{ig_user}/media", params=None if files else params, data=None if files else None,
                      files=files, timeout=600)
    if files:
        files["video_file"].close()
    create = r.json()
    print("[resp:create]", create)
    creation_id = create.get("id")
    if not creation_id:
        die("no creation id from /media", create)

    # Poll status
    print("[step] wait until ready…")
    for i in range(1, 31):
        time.sleep(5)
        status = requests.get(f"{GRAPH}/{creation_id}",
                              params={"fields":"status_code", "access_token": token},
                              timeout=30).json()
        print(f"[poll {i}] {status}")
        sc = (status or {}).get("status_code")
        if sc == "FINISHED":
            break
        if sc == "ERROR":
            die("container status ERROR", status, code=3)
    else:
        die("container never reached FINISHED", status, code=3)

    # Publish
    print("[step] publish…")
    pub = requests.post(f"{GRAPH}/{ig_user}/media_publish",
                        data={"creation_id": creation_id, "access_token": token},
                        timeout=60).json()
    print("[resp:publish]", pub)
    if "id" not in pub:
        die("publish failed", pub, code=4)

    print("[OK] published reel id:", pub["id"])

if __name__ == "__main__":
    main()
