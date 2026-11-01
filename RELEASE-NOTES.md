# Pod Themer 0.4.0 release candidate

- Every theme uses the icons and graphics already in the supplied firmware. No icon font files or generated icon rasters are included. Every indexed picture resource is checked byte for byte against the input.
- Enlarge uses Inter Tight Semibold at 13px for main text, with 11/10/11px secondary variants, 24px rows and the existing insets. Lossless column sharing lets the glyphs fit the original font allocations without shrinking or cropping them.
- Clear, Focus and Compact retain identical font bytes and spacing. Their firmware output hashes change because the original icons replace the previous third-party artwork. A migration audit compares previous/current bytes across all 20 builds.
- The familiar menus, Now Playing layout, centered metadata previews, device illustrations and wheel navigation remain. This release introduces no new screen layout or ARM instruction patches.
- Software checks are separate from hardware testing. This release has not run on an iPod. The app remains ad-hoc signed and unnotarized.

Final QA uses all five restored original IPSW archives, with ZIP integrity, exact payload hashes, internal names and manifest families verified. No firmware is distributed. See migration-verification.json and packaged-app-checks.json.
