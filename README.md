AI Show Starter (GitHub Actions cron)
- Generates stub assets and a dummy MP4 for multiple series (matrix build).
- Posts are STUBS; replace publisher code to hit real APIs.
- Artifacts (MP4) are uploaded to the Actions run for download.

Quick start
1) Create a new GitHub repo and upload these files.
2) In Settings → Secrets and variables → Actions, add:
   - OPENAI_API_KEY (optional for real generation)
   - IG_APP_ID, IG_APP_SECRET, IG_ACCESS_TOKEN, IG_PAGE_ID (if using IG Graph API)
   - TIKTOK_API_KEY (if using TikTok API)
3) Edit .github/workflows/daily.yml for cron time and series list.
4) Run the workflow manually (Actions → daily-episodes → Run workflow).
5) Check the artifacts for the rendered MP4(s).

Local test
- See infra/README_LOCAL.md for commands.
- Replace stubs in generator/ and assembly/ with actual generation logic.
