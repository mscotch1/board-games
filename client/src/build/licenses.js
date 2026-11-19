// The licenses of the third-party code the site ships to browsers, collected at build time.
//
// Many licenses (MIT, the font's OFL) require their text to travel with the software, so the
// build writes them all into /third-party-licenses.txt, which the About section links to.
// Only packages in the production tree are listed: development tools aren't shipped.

/** The production packages in an npm lockfile, as `{ name, version, license, path }`, sorted by name. */
export function productionPackages(lock) {
  return Object.entries(lock.packages ?? {})
    .filter(([path, info]) => path.startsWith('node_modules/') && !info.dev)
    .map(([path, info]) => ({
      // the last node_modules/ segment is the package name, which can be scoped (@scope/name)
      name: path.slice(path.lastIndexOf('node_modules/') + 'node_modules/'.length),
      version: info.version,
      license: typeof info.license === 'string' ? info.license : undefined,
      path,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

const LICENSE_FILE = /^(licen[sc]e|copying)(\.(md|txt))?$/i;

/** The name of the license file among a package's files, if it has one. */
export function findLicenseFile(fileNames) {
  return fileNames.find((name) => LICENSE_FILE.test(name)) ?? null;
}

/**
 * The text of the notices file. `readLicenseText(pkg)` gives a package's license text, or
 * null when it has none, in which case the notice says so rather than inventing one.
 */
export function formatNotices(packages, readLicenseText, header = '') {
  const divider = '='.repeat(78);
  const sections = packages.map((pkg) => {
    const text = readLicenseText(pkg);
    return [
      divider,
      `${pkg.name} ${pkg.version}`,
      `License: ${pkg.license ?? 'not stated in the package'}`,
      divider,
      '',
      text ? text.trim() : '(The package did not include a license file. Its license is as stated above.)',
      '',
    ].join('\n');
  });
  return [header.trim(), '', ...sections].join('\n') + '\n';
}
