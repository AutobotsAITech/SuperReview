# Website

The public site is [superreview.omnitensorlabs.com](https://superreview.omnitensorlabs.com/).

The project website is static HTML, CSS, and JavaScript in `site/`. It has no build step,
external fonts, analytics, or application backend.

Preview from the repository root:

```sh
python3 -m http.server 8000 --directory site --bind 127.0.0.1
```

Open `http://127.0.0.1:8000`. Check desktop and mobile layouts, keyboard navigation,
agent selection, and copying the installation command before publishing changes.

GitHub Pages serves the root of the `gh-pages` branch. To update it from a reviewed commit:

```sh
git subtree split --prefix site -b site-publish
git push origin site-publish:gh-pages
git branch -D site-publish
```

Use an unused temporary branch name. Do not force-push if the deployment branch has diverged.
Keep private review outputs and evaluation artifacts out of the website.

The `site/CNAME` file binds the custom domain. Its DNS CNAME points to
`autobotsaitech.github.io`; keep the file when publishing the website branch.
