# Third-party notices

The root [MIT license](LICENSE) covers original MR3 Control source code,
documentation, and project-created icons. It does **not** relicense third-party
fonts, photographs, dependencies, or trademarks.

## Pretendard

The unmodified files in `assets/fonts/Pretendard-*.ttf` are Pretendard v1.3.9.
Copyright (c) 2021, Kil Hyung-jin, with Reserved Font Name **Pretendard**.
They remain under the **SIL Open Font License 1.1**, whose complete copyright
notice and text are retained in [assets/fonts/LICENSE.txt](assets/fonts/LICENSE.txt).
That file must accompany redistributed font files. The app's MIT license does
not replace the font license.

See the [official OFL bundling guidance](https://openfontlicense.org/ofl-faq/)
and [asset sources](assets/SOURCES.md).

## Edifier photograph and trademarks

`assets/mr3-product.png` is an official Edifier product photograph. Copyright
remains with Edifier. It is excluded from the project's MIT grant; this project
does not grant permission to reuse or redistribute that photograph. Its source
is recorded in [assets/SOURCES.md](assets/SOURCES.md).

Edifier and its product names/trademarks belong to their respective owners.
This project is unofficial and is not endorsed by Edifier.

## Runtime and dependencies

Python, Tcl/Tk, Bleak, Pillow, pystray, WinRT bindings, and build tools retain
their respective licenses. `packaging/collect_licenses.py` collects the build
environment's notices and dependency inventory into the bundled
`_internal/licenses/` directory. Additional notice copies live in `packaging/`.
An entry in the inventory does not imply that a build-only tool is shipped.
