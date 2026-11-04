import type { PyodideAPI } from 'pyodide'

import { BOOT_PY, KERNEL_FILES } from './protocol'

/**
 * Mount the backend's pure Python modules into a Pyodide instance and import app.kernel.
 * Shared by the browser worker and the opt-in Node test (kernel.e2e.test.ts), so both run the
 * exact same setup. `files` maps a KERNEL_FILES path to its source text.
 */
export async function mountKernel(py: PyodideAPI, files: Record<string, string>): Promise<void> {
  // pydantic (and its Rust core) ship in the Pyodide distribution; nothing else is needed.
  await py.loadPackage(['pydantic'], { messageCallback: () => undefined })
  const root = '/home/pyodide/kernel'
  for (const rel of KERNEL_FILES) {
    const src = files[rel]
    if (src === undefined) throw new Error(`kernel file missing from bundle: ${rel}`)
    const path = `${root}/${rel}`
    py.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')))
    py.FS.writeFile(path, src)
  }
  py.runPython(BOOT_PY)
}
