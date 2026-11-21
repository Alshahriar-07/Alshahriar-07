# Fonts

Subset WOFF builds are embedded directly into the generated SVG cards as base64
`data:` URIs. The build only embeds the faces a card uses and re-subsets them to
that card's character set (`scripts/svg_kit.py`), so the glyphs stay small.

| File | Family | Used for |
| --- | --- | --- |
| `serif-400.woff` | Instrument Serif 400 | display headings, project names |
| `serif-italic.woff` | Instrument Serif 400 italic | italic accents |
| `geist-400.woff` | Geist 400 | body copy, captions |
| `geist-600.woff` | Geist 600 | emphasized labels |
| `geistmono-400.woff` | Geist Mono 400 | terminal lines, metadata |

All three families are licensed under the
[SIL Open Font License 1.1](https://openfontlicense.org). The files here are
printable-ASCII subsets (plus a few arrows and symbols) and are redistributed
under the same license. They are design assets, not code, and are never executed.
