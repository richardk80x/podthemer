# Third-party notices

The Pod Themer app/engine source and numeric resource metadata use the accompanying MIT license. No Apple firmware or SF Compact font raster patches are distributed in this release.

## Theme fonts

- Inter Tight: SIL Open Font License 1.1. Full notice: `assets/fonts/INTER-TIGHT-OFL.txt`. Unmodified source: https://github.com/google/fonts/tree/main/ofl/intertight
- Inter: SIL Open Font License 1.1. Full notice: `assets/fonts/INTER-OFL.txt` in source, and the corresponding bundled engine asset.
- Roboto Condensed: SIL Open Font License 1.1. Full notice: `assets/fonts/ROBOTO-CONDENSED-OFL.txt`.
- Atkinson Hyperlegible (source asset): SIL Open Font License 1.1. Full notice: `assets/fonts/ATKINSON-OFL.txt`.

Open font files are bundled unmodified. The canonical replacement glyph raster collections are named for the Pod Themer themes and are covered by their source fonts’ OFL notices. Original icons remain in the user-supplied firmware and are neither bundled nor copied into the raster cache. The cache omits stock glyph images. Firmware builds preserve original font headers and maps for compatibility; unsupported replacement glyphs remain from the user's own original firmware. Existing firmware font-selector names therefore do not identify the replacement asset's family. Reports identify the source font used. No retained Apple glyph bytes are shipped in the app.

## Bundled runtime

Python 3.14.7 (Python Software Foundation license and associated notices), Pillow 12.3.0 (HPND and upstream dependency licenses), and the PyInstaller 6.22.3 bootloader (GPL with the upstream distribution exception) support the standalone engine. Full license text and wheel-supplied dependency notices are included in `Contents/Resources/Runtime-Licenses` in the app. Refer to the included upstream terms for precise coverage.

## App icon

The Pod Themer icon was generated for this project using OpenAI's built-in image generation tool. The prompt and generation provenance are in `assets/AppIcon-provenance.md` in the source package. It depicts a generic monochrome music player and a paintbrush, without an Apple logo. Pod Themer is an unofficial independent project and is not affiliated with Apple.
