# The Cool League

Static archive site for The Cool League (ESPN league 71154576), 2020–present.

Deployed as a Cloudflare Worker with static assets. Everything the site needs
is in `public/`; `wrangler.jsonc` points the Worker at that directory.

    public/index.html     the entire site (no build step, no framework)
    public/archive.json   every game and player line, read at runtime
    public/news/          newsletter scans and photos

## Updating

Replace `public/index.html` and `public/archive.json`, commit, push.
Cloudflare redeploys on push to `main`.
