# Chart.js (vendored)

- Package: `chart.js`
- Version: **4.5.1** (exact, UMD build)
- File: `chart.umd.js` (from `package/dist/chart.umd.js` of the npm tarball)
- Source: https://registry.npmjs.org/chart.js/-/chart.js-4.5.1.tgz (`npm pack chart.js@4.5.1`)
- License: MIT, see `LICENSE.md`
- SHA-256 of the file as shipped here: `84D0E233DABA702B8F77D669D8C137CAD36D441A10F200B6F2D3AB553BDFCF6B`
- SHA-256 of the file inside the npm tarball (before the edit below): `ECC3CD1EEB8C34D2178E3F59FD63EC5A3D84358C11730AF0B9958DC886D7652A`

Served locally through `{% static 'vendor/chartjs/chart.umd.js' %}`. There is no CDN at runtime.

## One local edit

The last line of the upstream file, `//# sourceMappingURL=chart.umd.js.map`, was removed. The map is not
vendored, and WhiteNoise's `CompressedManifestStaticFilesStorage` fails `collectstatic` on a reference to a
file that does not exist. Nothing else in the file was changed.

## How to update

1. `npm pack chart.js@<new 4.x version>` in a scratch folder and extract the tarball.
2. Copy `package/dist/chart.umd.js` and `package/LICENSE.md` over the files here.
3. Delete the trailing `//# sourceMappingURL=...` line again.
4. Update the version and both hashes above (`Get-FileHash chart.umd.js -Algorithm SHA256`).
5. Run `tests/statistics/test_static_manifest.py` (`pytest -m slow`) and the rest of `tests/statistics`.
