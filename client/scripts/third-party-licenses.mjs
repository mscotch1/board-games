// Writes public/third-party-licenses.txt: the licenses of the third-party code the site ships.
// It runs before every build (see "prebuild" in package.json); the result is served at
// /third-party-licenses.txt and isn't committed.

import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { findLicenseFile, formatNotices, productionPackages } from '../src/build/licenses.js';

const root = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const lock = JSON.parse(readFileSync(join(root, 'package-lock.json'), 'utf8'));

function readLicenseText(pkg) {
  const directory = join(root, pkg.path);
  const file = findLicenseFile(readdirSync(directory));
  return file ? readFileSync(join(directory, file), 'utf8') : null;
}

const header = `
Third-party software in Monka Games

This site is free software under the GNU Affero General Public License, version 3 or
later; see the LICENSE file in its source code. It includes the following third-party
software, each under its own license, reproduced below.
`;

const packages = productionPackages(lock);
writeFileSync(join(root, 'public', 'third-party-licenses.txt'), formatNotices(packages, readLicenseText, header));
console.log(`third-party-licenses.txt: ${packages.length} packages`);
