# Privacy and hosting

Guard processes selected images and GRD files locally. The application sends no file contents to an API, adds no analytics, and does not save selected files in localStorage, IndexedDB or a service worker. Browser memory is used while a file is open; explicitly downloaded files remain on your device. The offline HTML is captured before any file is selected.

The hosted site is served by GitHub Pages. GitHub states that it logs and stores visitors' IP addresses for security regardless of login. This hosting request is separate from processing a selected file. See [GitHub Pages data collection](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages#data-collection) and [GitHub's Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). External source/privacy links also contact their destination when opened. The page sets a no-referrer policy.

For use without contacting the host, download the standalone viewer from a trusted source and open that local file after disconnecting. An offline viewer still needs your browser's crypto/stream APIs. Browser extensions, the operating system, screenshots and copies held by other people are outside Guard's control.

New browser conversions use an empty signed label and the generic download name `image.GRD`; the source filename is shown only in the local selection preview. The source EXIF metadata is not copied. Existing containers can include public labels, names and other signed metadata; reports can contain these too. Review files and reports before sharing. Signer fingerprints, dimensions, retained pixels, tile commitments and redaction information are public container data.

Exports replace every hidden tile with solid black, omit its original salt, and do not embed source/recovery files. They also sanitize previously hidden regions when re-exporting an older blur file. Earlier blur exports may already disclose details and should not be treated as anonymised. A method field is an unsigned claim, not proof of the operation performed. Anyone with the original still has its pixels; this is not DRM or a guarantee that a person cannot be identified from retained context.

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
