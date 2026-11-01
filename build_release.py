#!/usr/bin/env python3
"""Build a self-contained Apple Silicon macOS app; never publish or notarize it.

Run with a redistributable Python 3.14 runtime supporting macOS 14 or earlier,
with requirements-build.txt installed. Developer ID signing is optional via
PODTHEMER_SIGN_IDENTITY; absent that identity the result is an ad-hoc signed RC.
"""
from pathlib import Path
import argparse, importlib.metadata, json, os, plistlib, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
VERSION = '0.4.0'


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    if output.exists():
        raise SystemExit('Output app already exists; choose a new output path.')
    identity = os.environ.get('PODTHEMER_SIGN_IDENTITY', '-')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', 'PodThemerEngine', '--target-architecture', 'arm64',
               '--distpath', str(work/'dist'), '--workpath', str(work/'pyinstaller'),
               '--specpath', str(work),
               '--exclude-module', 'tkinter', '--exclude-module', 'PIL.ImageTk']
    if identity != '-':
        command += ['--codesign-identity', identity]
    for name in ('themes.json', 'resource-map.json', 'device-profiles.json', 'profiles', 'assets/fonts', 'assets/theme-rasters.json.gz'):
        dest = 'profiles' if name == 'profiles' else ('assets/fonts' if name == 'assets/fonts' else ('assets' if name.startswith('assets/') else '.'))
        command += ['--add-data', f'{ROOT/name}:{dest}']
    command.append(str(ROOT/'theme_engine.py'))
    run(*command)
    stage = Path(tempfile.mkdtemp(prefix='app-stage-', dir=work))/'Pod Themer.app'
    contents = stage/'Contents'; resources = contents/'Resources'; macos = contents/'MacOS'
    resources.mkdir(parents=True); macos.mkdir()
    helpers = contents/'Helpers'; helpers.mkdir()
    shutil.copytree(work/'dist/PodThemerEngine.app', helpers/'PodThemerEngine.app', symlinks=True)
    for name in ('themes.json', 'README.md', 'LICENSE.txt', 'THIRD-PARTY-NOTICES.md', 'COMPATIBILITY.md', 'RELEASE-NOTES.md', 'FONT-CHOICE.md'):
        shutil.copy2(ROOT/name, resources/name)
    shutil.copy2(ROOT/'assets/PodThemer.icns', resources/'PodThemer.icns')
    license_root = resources/'Runtime-Licenses'
    license_root.mkdir()
    python_license = Path(sys.base_prefix)/f'lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt'
    shutil.copy2(python_license, license_root/'PYTHON-LICENSE.txt')
    for package in ('Pillow', 'PyInstaller'):
        dist = importlib.metadata.distribution(package)
        for file in dist.files or []:
            if 'licenses' in file.parts:
                source = dist.locate_file(file)
                if source.is_file():
                    index = file.parts.index('licenses')
                    destination = license_root/package/Path(*file.parts[index+1:])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    run('xcrun', 'swiftc', '-target', 'arm64-apple-macosx14.0', '-swift-version', '5',
        '-parse-as-library', '-O', '-module-cache-path', work/'swift-cache',
        ROOT/'PodThemer.swift', '-o', macos/'PodThemer')
    plist = dict(CFBundleExecutable='PodThemer', CFBundleIdentifier='app.podthemer.mac',
                 CFBundleName='Pod Themer', CFBundleDisplayName='Pod Themer', CFBundlePackageType='APPL',
                 CFBundleShortVersionString=VERSION, CFBundleVersion='6', LSMinimumSystemVersion='14.0',
                 CFBundleIconFile='PodThemer.icns', NSHighResolutionCapable=True,
                 NSHumanReadableCopyright='© 2026 Pod Themer contributors. Unofficial; not affiliated with Apple.')
    (contents/'Info.plist').write_bytes(plistlib.dumps(plist))
    signing = ['codesign', '--force', '--sign', identity]
    if identity != '-':
        signing += ['--options', 'runtime', '--timestamp']
    run(*signing, stage)
    run('codesign', '--verify', '--deep', '--strict', stage)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(stage), output)
    print(json.dumps(dict(app=str(output), version=VERSION, architecture='arm64',
                          minimum_macos='14.0', developer_id_signed=identity!='-', notarized=False)))


if __name__ == '__main__':
    main()
