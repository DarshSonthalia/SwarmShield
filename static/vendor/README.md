# Vendored Three.js runtime

SwarmShield vendors the official Three.js **r186** release (`0.186.0`) so the
dashboard works offline without npm or a runtime CDN.

Downloaded 2026-09-25 from the immutable upstream tag:

- `three.module.js`: https://raw.githubusercontent.com/mrdoob/three.js/r186/build/three.module.js
- `three.core.js`: https://raw.githubusercontent.com/mrdoob/three.js/r186/build/three.core.js
- `OrbitControls.js`: https://raw.githubusercontent.com/mrdoob/three.js/r186/examples/jsm/controls/OrbitControls.js
- `LICENSE`: https://raw.githubusercontent.com/mrdoob/three.js/r186/LICENSE

SHA-256:

- `three.module.js`: `9052042D676CB0FDC1DDFEFE193053F34B7AC0513A616FDAC4535D49987812EA`
- `three.core.js`: `9EDDE002B066A9A05676A6127F67735B62BAF399BDEA529F2F7E31657DA769E6`
- `OrbitControls.js`: `3D79D07ECB686B4E5D93232EEDAB255331C1BEEF711E13164EAA1F68655A5F2B`
- `LICENSE`: `8B378EBE60E2FE500158CB0AC71CB5E8B7D92953C2ABCC63A0EB90499653B5BC`

The import map in `static/index.html` resolves OrbitControls' upstream bare
`three` import to the local module. The vendored JavaScript files are unmodified.
