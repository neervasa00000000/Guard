# Privacy, plainly. Effective 27 October 2026.

**Who runs this.** Guard is an open-source project published at [github.com/neervasa00000000/Guard](https://github.com/neervasa00000000/Guard). Questions or privacy requests: [https://github.com/neervasa00000000/Guard/issues](https://github.com/neervasa00000000/Guard/issues).

**What Guard does with your files.** Images and .GRD files you choose are read, checked and converted only inside your browser. Guard does not upload their contents, use analytics, cookies or trackers, or store files in localStorage, IndexedDB or a service worker. Files you download stay on your device.

**What the website host collects.** This site is served by GitHub Pages. When your browser loads the page, GitHub receives standard request data, including your IP address, and logs it for security, even if you are not signed in to GitHub. Guard cannot see or control those logs. See [GitHub Pages data collection](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages#data-collection) and the [GitHub General Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). To avoid contacting the host, use Download offline viewer, disconnect, and open the saved file.

**Personal information inside files.** A .GRD can contain a public label, signer name, signer fingerprint, image dimensions, retained pixels and a list of hidden areas. Labels and file names may identify people, for example "passport_jane_smith.jpg". New browser conversions leave the label blank and download as image.GRD. Verification reports you save include these details. Check files and reports before sharing them.

**Redaction limits.** Exports replace hidden areas with solid black. Anyone who already has the original or an earlier copy still has those pixels. Surrounding details can still identify a person.

**Links.** Opening the source or privacy links contacts those sites. This page sends no referrer.

## Embedding

The application refuses to initialize inside a frame and shows an open-directly message. This JavaScript guard is a fallback, not a browser-enforced framing policy; it is not a complete clickjacking guarantee, especially when scripts are disabled or modified.

For browser-enforced protection, serve these HTTP response headers through your host or reverse proxy:

```
Content-Security-Policy: frame-ancestors 'none'
X-Frame-Options: DENY
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
```

The included `_headers` file configures compatible hosts such as [Cloudflare Pages](https://developers.cloudflare.com/pages/configuration/headers/). It is not applied by the current GitHub Pages deployment. Do not claim the live site has these response headers merely because the file exists. The [CSP specification](https://www.w3.org/TR/CSP/#directive-frame-ancestors) requires `frame-ancestors` in an HTTP header; it is ignored in a meta policy. A host/proxy with response-header control is needed for that remaining protection.
