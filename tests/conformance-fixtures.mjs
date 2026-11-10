// SPDX-License-Identifier: MIT
import { execFileSync } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

export async function withConformanceFiles(check) {
  const directory = await mkdtemp(join(tmpdir(), 'tileseal-conformance-'));
  try {
    execFileSync('python3', [join(root, 'scripts/large_conformance_fixtures.py'), directory]);
    return await check(vector => vector.generated
      ? join(directory, basename(vector.file))
      : join(root, vector.file));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}
