# Assets

- `mr3-product.png`: Edifier MR3 official product photograph, retrieved from
  https://new-edifier-us-oss.edifier.com/images/20240904/dd1e9b43755dd4c1919277d05885c64a.png
  via https://www.edifier.com/global/p/studio-monitors/mr3 . Copyright belongs to Edifier.
- `fonts/Pretendard-*.ttf`: Pretendard v1.3.9, official release source
  https://github.com/orioncactus/pretendard/tree/v1.3.9/packages/pretendard/dist/public/static/alternative .
  The bundled SIL Open Font License is in `fonts/LICENSE.txt`.
- `mr3.ico`, `mr3.png`: speaker glyph rendered by `tools/make_icon.py`.
- Button/navigation icons: line drawings rendered by `src/mr3_icons.py`.

Product photo and fonts are loaded locally at runtime; the app does not request network assets.
