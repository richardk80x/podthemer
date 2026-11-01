# Releasing Pod Themer

Release 0.4.0 is prepared as an Apple Silicon macOS 14+ release candidate. No publication is performed by the build scripts.

1. Run the engine tests against an owner-supplied exact stock IPSW. Verify the current payload baselines and the migration audit and Enlarge's 13/11/10/11px sizes, byte-identical original firmware pictures, protected resources, checksums, and export integrity.
2. Build with `requirements-build.txt` and an appropriate redistributable Python. Verify every bundled Mach-O dependency's deployment target, not only the Swift executable. Run packaged-engine tests with no external Python path or build environment variables. Test the app on clean supported macOS machines. Intel is not supported by the current artifact.
3. Use your Apple Developer ID Application identity through `PODTHEMER_SIGN_IDENTITY` when rebuilding. PyInstaller signs the helper and its native dependencies; the build signs the containing app with hardened runtime when a Developer ID is supplied. Do not substitute ad-hoc signing for this release step.
4. ZIP the signed app with `ditto -c -k --keepParent`. Submit that archive using `xcrun notarytool submit ARCHIVE --keychain-profile YOUR_PROFILE --wait`. Review failures rather than suppressing them. After acceptance, use `xcrun stapler staple APP` and `xcrun stapler validate APP`; verify `codesign --verify --deep --strict APP` and Gatekeeper assessment on a clean system. Do not place credentials in source or release files.
5. Create the final ZIP from the stapled app, update its SHA-256 checksum and release validation report, and publish the app archive, source archive, release notes, compatibility matrix, license notices, and checksums. Publish only the builder; do not bundle Apple IPSWs or legacy SF Compact raster patches.
6. Keep support claims limited to the five implemented exact firmware profiles. Clearly label their software-only validation; other versions and variants are unsupported. Collect real hardware results for this version of every theme before claiming device testing.

The current environment has no Developer ID identity, so the supplied candidate remains ad-hoc signed and unnotarized. App/engine tests do not replace those publisher steps or device tests.

References: [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [PyInstaller macOS signing](https://pyinstaller.org/en/stable/feature-notes.html#macos-specific-options).
