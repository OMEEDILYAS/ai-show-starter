import argparse
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    args = ap.parse_args()
    print(f"[analytics] (stub) collected metrics for {args.series}")
if __name__ == "__main__":
    main()
