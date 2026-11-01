# Pod Themer 0.4.0 - release candidate

A standalone macOS app for giving Apple's original monochrome iPod firmware a choice of four complete themes.

## Install and use

Unzip the Apple Silicon release, move **Pod Themer.app** to Applications, and open it. Python, Pillow, a shell launcher, and network access are not needed at runtime. The current app targets Apple Silicon Macs running macOS 14 or later. Intel and Windows builds are not included.

Choose an original supported monochrome iPod IPSW. The app verifies its contents and manifest, identifies its device family, and shows a matching model-specific device illustration. Gen 1/2 share a firmware profile; Gen 3 has its separate button row; Mini uses its smaller screen and case. Identification does not rely on the outer filename or inspect a connected iPod. Choose a theme, preview Main Menu/Music/Settings/Now Playing, and build to a new output filename.

The app exports a custom IPSW, a validation report, and a reconstructed preview. It does not download or flash firmware. Installation is a separate restore operation that can erase the device; back up your music before restoring. Your original IPSW stays unchanged. Previews are not an emulator or hardware screenshots.

## Four complete themes

| Theme | Open font | Main size | Secondary variants | Menu pitch | Icons |
| --- | --- | --- | --- | --- | --- |
| Clear | Inter Medium | 12px | 11/10/11px | 24px | Original firmware |
| Focus | Roboto Condensed Bold | 14px | 11/10/11px | 26px | Original firmware |
| Compact | Inter Regular | 12px | 10/9/10px | 20px | Original firmware |
| Enlarge | Inter Tight Semibold | **13px** | **11/10/11px** | **24px** | Original firmware |

**Enlarge keeps the enlarged font sizes and spacing of the original custom Readable v1 theme, using Inter Tight Semibold and the supplied firmware’s original icons.** It is larger than Apple's stock main text; it is not a return to stock font size. The build fails if Enlarge cannot fit the specified sizes; it never silently scales them down. Inter Tight Semibold was selected by comparing 13px monochrome rendering and string widths with the original SF Compact Text Semibold. It is a close alternative, not an identical copy; see `FONT-CHOICE.md`. Enlarge uses lossless sharing of identical bitmap columns to fit the fixed allocations without reducing font size. New Enlarge output is not byte-identical to that earlier build.

Clear, Focus, and Compact retain their established font bytes and spacing. All theme payload hashes change in 0.4.0 because their original firmware icons are restored. Enlarge also changes to a 13px semibold open font. No individual font/style controls are exposed.

## Supported firmware

Exact profiles are implemented for the supplied Gen 1/2 1.5, Gen 3 2.3, 4G monochrome 3.1.1, Mini 1 1.4.1 and Mini 2 1.4.1 images. See `COMPATIBILITY.md` for exact outer/internal filenames and test status. Each profile has its own resource map and checksum convention; no 4G patch offsets are reused on another family.

The app bundles no Apple firmware. Other firmware hashes and manifest families remain rejected, including unimplemented variants within an otherwise supported generation. These are software-validated experimental outputs, not hardware-tested firmware releases.
## Validation and release status

All output changes are restricted to font metrics/bitmaps, menu spacing/insets, and the OS checksum. All supplied firmware picture resources are preserved byte for byte. Original menu definitions, commands, text resources, font headers/Unicode maps, payload length, manifest, and flash updater are checked for preservation. Exported archives are reopened and verified.

Software checks and local app/runtime tests do not establish hardware compatibility. The user reported an earlier private Readable v1 working on a 4G iPod. This release's open-font Enlarge and the other themes have no recorded hardware test. See the release validation report for exact checks.

The available release candidate is ad-hoc signed because no Developer ID identity was available in the build environment. It is **not notarized** and is not yet the final Gatekeeper-trusted public release. Do not represent it as notarized. See `RELEASING.md` for the final Developer ID signing, notarization, and release steps. No Gatekeeper-disabling workaround is part of this package.

## Source builds and tests

Replacement open-font glyphs are stored in a canonical raster cache, so installed text-shaping libraries cannot change firmware output. No icon font files or generated icon rasters are bundled. The cache excludes unchanged stock glyph pixels; those are read from the user’s firmware. `freeze_theme_rasters.py` regenerates it using the recorded RAQM-enabled renderer and an owner-supplied raw stock payload; baseline checks must pass afterward.

The end-user app is self-contained. Source development requires Python and Pillow; native builds additionally require macOS and Apple's Swift tools. Install `requirements-build.txt` into an isolated environment using a redistributable Python whose macOS deployment target is no newer than 14.0. Do not use a host-only Python built for a newer macOS release when claiming macOS 14 support.

Run `build_release.py --work WORK_DIRECTORY --output NEW_APP_PATH` with that environment's Python. It bundles the engine using PyInstaller and compiles/signs the native app. `PODTHEMER_SIGN_IDENTITY` optionally selects your Developer ID identity. The build script does not publish or notarize automatically.

Set `PODTHEME_TEST_IPSW` to your original IPSW and run `python3 -m unittest -v test_engine`. `device-profiles.json` maps exact firmware identity to supported model metadata and preview style. Do not add unsupported model claims without implementing and testing their resource maps. Set `PODTHEMER_TEST_FIRMWARE_DIR` to a directory containing the five original images to run `test_profiles.py` as well.

## Privacy and licenses

The app works locally, does not contact a server, and does not read connected devices. Inputs and outputs remain on your computer. Open fonts, bundled runtime notices, and the independent MIT app code are documented in `THIRD-PARTY-NOTICES.md`. This is an unofficial project, not affiliated with Apple.
