# Pyodide 314.0.8 (self-hosted, SEC-03)

These are the core runtime files from the npm package `pyodide@314.0.8`
(https://registry.npmjs.org/pyodide/-/pyodide-314.0.8.tgz). The tarball's sha512
matched the registry's `dist.integrity` value before extraction. Pyodide is
licensed under the Mozilla Public License 2.0 (https://github.com/pyodide/pyodide).

They are served from this site instead of a CDN, so the page runs no third-party
code and the CSP can allow scripts from `'self'` only. Only the files the game
needs are kept (no source maps, type definitions or console pages); the game uses
only the standard library, so no extra packages are loaded.

To upgrade: download the new tarball, check its integrity, copy the same files,
update the version here, rebuild docs/ and rerun the browser check.

SHA-256 of the copied files:

```
d4e1e0f06c29162eadf0c3f323c746884242b257d1faa94760442a4ac929e9a1  pyodide.js
22514b8be6980e28a02c8b1d6387ce8dfe666fc4edf8d547cff5dce29ff4d972  pyodide.asm.mjs
e14d49ceca9b4a0e274ea918f3a898de2d3880b6e5573a6cfe1a2267ecc70329  pyodide.asm.wasm
2bd3394a145bfbbe5bbc9d9d6ab9136abbb986c6fef6c142b3a2962227aa5c28  python_stdlib.zip
5dc2fc119108bc148c7457dc86e7675b5c87e1cafd420b9c34c1eaef7b36c010  pyodide-lock.json
```
