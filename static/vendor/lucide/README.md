# Lucide icons (vendored subset)

- Package: `lucide-static@1.52.0` (npm)
- Tarball integrity: `sha512-0zZYihAze4ZmUCcyNa9OkWYqn/Y5f9AdTh02AZIxMtP5ravcTTfoSIAnUPBH6ZvKxt+ZW28JB0ldzLRyD82fcw==`
- Tarball shasum: `ed1a4f3e64f06e30a50d7898fa1f7a4c33545218`
- License: ISC (see `LICENSE`)
- Upstream: https://lucide.dev

`sprite.svg` is a subset: only the ids listed in `apps/core/icons.py: ICON_NAMES`,
each as `<symbol id="lucide-<name>">`. Templates use `{% icon 'name' %}` from
`core_tags`; JavaScript uses `BrgyUI.icon('name')` from `static/js/icons.js`.

Rebuild after adding a name to `ICON_NAMES`:

```powershell
mkdir scratch\lucide; cd scratch\lucide
npm pack lucide-static@1.52.0
tar -xzf lucide-static-1.52.0.tgz
cd ..\..
python manage.py build_icon_sprite --source scratch\lucide\package\icons
Remove-Item -Recurse scratch\lucide
```
