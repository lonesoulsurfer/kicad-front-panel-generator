"""Build the KiCad Plugin and Content Manager (PCM) repository for the 'Open Panel Generator' button.

    python tools/make_pcm.py

Makes, in pcm/:
    panel-generator-button_v<version>_pcm.zip   the package (Install from File... in KiCad takes this too)
    packages.json, resources.zip, repository.json
KiCad users add this repository in the Plugin and Content Manager (Manage... > +) with the URL
    https://raw.githubusercontent.com/lonesoulsurfer/kicad-front-panel-generator/main/pcm/repository.json
Run it again after changing anything in kicad-plugin/ (and raise the version in kicad-plugin/metadata.json), then commit pcm/.
"""
import hashlib, json, os, time, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'kicad-plugin')
OUT = os.path.join(ROOT, 'pcm')
RAW = 'https://raw.githubusercontent.com/lonesoulsurfer/kicad-front-panel-generator/main/pcm/'
FIXED = (2026, 1, 1, 0, 0, 0)          # fixed dates inside the zip: the same files make the same zip (same hash)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(65536), b''):
            h.update(b)
    return h.hexdigest()


def add(z, path, name):
    info = zipfile.ZipInfo(name, FIXED)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with open(path, 'rb') as f:
        z.writestr(info, f.read())


def resource(path):
    return dict(url=RAW + os.path.basename(path), sha256=sha(path), update_timestamp=int(time.time()),
                update_time_utc=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()))


def main():
    meta = json.load(open(os.path.join(SRC, 'metadata.json'), encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)
    ver = meta['versions'][0]['version']
    pkg = os.path.join(OUT, f"panel-generator-button_v{ver}_pcm.zip")
    files = [('metadata.json', os.path.join(SRC, 'metadata.json')), ('LICENSE', os.path.join(SRC, 'LICENSE')),
             ('resources/icon.png', os.path.join(SRC, 'resources', 'icon.png'))]
    for n in sorted(os.listdir(os.path.join(SRC, 'plugins'))):
        p = os.path.join(SRC, 'plugins', n)
        if os.path.isfile(p) and not n.endswith('.pyc'):
            files.append(('plugins/' + n, p))
    with zipfile.ZipFile(pkg, 'w') as z:
        for name, path in files:
            add(z, path, name)
    install = sum(os.path.getsize(p) for _, p in files)
    entry = dict(meta)
    entry['versions'] = [dict(meta['versions'][0], download_url=RAW + os.path.basename(pkg), download_sha256=sha(pkg),
                              download_size=os.path.getsize(pkg), install_size=install)]
    entry.pop('$schema', None)
    packages = os.path.join(OUT, 'packages.json')
    with open(packages, 'w', encoding='utf-8') as f:
        json.dump({'packages': [entry]}, f, indent=4)
    res = os.path.join(OUT, 'resources.zip')
    with zipfile.ZipFile(res, 'w') as z:
        add(z, os.path.join(SRC, 'resources', 'icon.png'), meta['identifier'] + '/icon.png')
    repo = {'$schema': 'https://go.kicad.org/pcm/schemas/v1#/definitions/Repository', 'name': 'Panel Generator (lonesoulsurfer)',
            'maintainer': {'name': 'Marcus (lonesoulsurfer)', 'contact': {'web': 'https://github.com/lonesoulsurfer/kicad-front-panel-generator'}},
            'packages': resource(packages), 'resources': resource(res)}
    with open(os.path.join(OUT, 'repository.json'), 'w', encoding='utf-8') as f:
        json.dump(repo, f, indent=4)
    print('made', os.path.relpath(pkg, ROOT), 'and', os.path.relpath(OUT, ROOT) + '/repository.json')


if __name__ == '__main__':
    main()
