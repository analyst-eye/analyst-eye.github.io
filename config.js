/* Analyst Eye site config — the ONE place to set your public URL.
   After changing SITE_URL here, run:  python3 tools/set_site_url.py
   (that copies it into the twitter:player / og meta tags, which X reads without running JS).
   The GitHub Actions deploy also does this automatically using your Pages URL. */
window.AE_CONFIG = {
  SITE_URL: "https://analyst-eye.github.io/",
  HANDLE: "A_is_A",
  LAUNCH_DATE: "2026-10-19",          // puzzle #1 (US Central date)
  TIMEZONE: "America/Chicago",
  ROUND_SECONDS: 30,
  HINT_PENALTY: 25
};
