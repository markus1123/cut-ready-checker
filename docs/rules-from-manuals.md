# Rules from manufacturer manuals

What the manufacturers' own documents say, as numbers a checker can test against. All sources were fetched on **2026-11-22**.
Local copies are in `docs/sources/`, which is git-ignored because the manuals are copyrighted. "p" means the page of the PDF file. "cat. p" means the page number printed in the catalogue.

Legend: **OK** = the generator agrees with the source. **DISAGREE** = the generator differs from the source. **NOT FOUND** = I found no official public source, so no rule is given.

---

## 1. Hettich KA 4532 ball-bearing runner (Silent System), art. 9114274, 400 mm

Sources:
- Product page: https://shop.hettich.com/no_EN/p/9114274. Technical-data table. Not saved, because it is a web page.
- Mounting instructions MS 10547.00.000: https://web2.hettich.com/hbh/addon/montage/MS_10547_00_Montageanleitung_KA4532-SiSy.pdf, saved as `hettich_MS_10547_00_Montageanleitung_KA4532-SiSy.pdf`
- Quality criteria: https://web2.hettich.com/hbh/addon/montage/Qualitaetskriterien_Holz_Auszugsfuehrungen_EN.pdf, saved as `hettich_Qualitaetskriterien_Holz_Auszugsfuehrungen_EN.pdf`

Not saved:
- CAD zip: https://web2.hettich.com/hbh/addon/cad/9114274_3d.zip
- Catalogue page bk_818.pdf, which returned 404.

| Rule | Value | Where |
|---|---|---|
| Runner section (H x W) | 46 x 12.7 mm, screw line at 23 mm (centre) | MS 10547 p1, top drawing |
| Side clearance, per side | **12.7 +0.8 mm**, so 12.7 to 13.5 mm | MS 10547 p1, top drawing |
| Max drawer width (recommendation) | **550 mm** | MS 10547 p1, top drawing ("max. 550 (Empfehlung)") |
| Screws | Cabinet side: Ø4 x 14 chipboard screw or Ø6 x 14 system screw. Drawer side: Ø4 x 14 | MS 10547 p1 |
| Min. inside cabinet depth | **drawer length + 4 mm**. For /400 that is 404 | MS 10547 p2 footnote; shop page "KT 404" |
| Runner set back from cabinet front edge | 2 mm | MS 10547 p2, all lengths |
| **/400 cabinet-member holes**, measured from the cabinet front edge | **37, 165 (37+128), 229 (37+192)** | MS 10547 p2, KA 4532/400 |
| **/400 drawer-member holes**, measured from the drawer front datum (the X = 400 line) | **37, 165 (37+128), 291 (37+254)** | MS 10547 p2, KA 4532/400 (detail rendered at 4x) |
| Same front hole at 37 mm for every length | 300 to 700 | MS 10547 p2 |
| Hole types in the runner | Ø4.4 round, Ø4.4 x 4 slot, Ø6.4. The slot group spans **64**: 9 / 16 / 24.5 / 20 | MS 10547 p2, detail "i" |
| Load capacity | 35 kg, stated for a 500 mm reference length (DIN EN 15338) | shop page; quality criteria p1 |

**The b1/C contradiction is resolved.** On the shop page for 9114274, b1 = 64 and C = 254.
- **254** is the drawer-member span from the first hole (37) to the rear hole (291).
- **64** is the span of the cabinet-member slot group in detail "i".
- "96" appears only in the drawer-member patterns for /500 and /550. "292" does not appear anywhere in this drawing.
- So **96/292 belongs to another length or variant, not to the /400.**

Generator (`beslag/skinne.json`, `params.json`):
- `sideklaring` 12.7 + `sideklaring_tillegg` 0.3 = 13.0. **OK**, it is inside 12.7 to 13.5.
- `min_innvendig_dybde` 404. **OK**.
- `hoyde` 46. **OK**.
- `korpus_hull` and `skuff_hull` are empty. They can now be filled from MS 10547 p2: cabinet 37/165/229 and drawer 37/165/291. The datum and the 2 mm set-back still need to be confirmed on the physical runner.
- `skrue_lengde` 16 vs Ø4 x 14 in the manual. **DISAGREE (minor).** A 16 mm screw is still fine in 19 mm board.
- **DISAGREE (important): drawer width.** From `params.json`: opening = (1603 - 3 x 19) / 2 = 773 mm, so the drawer box is about 773 - 2 x 13.0 = **747 mm wide**. Hettich recommends at most **550 mm** for the KA 4532.

## 2. Häfele Minifix 15 (housing + bolt)

Source: Häfele UK "TCH Technology 2023" catalogue, section 7. Each page is saved as `hafele-uk_23T7-<page>.pdf` and fetched from `https://files.hafele.co.uk/CatalogFiles/www/23T7-<page>.pdf`.

| Rule | Value | Where |
|---|---|---|
| Housing bore | Ø15 | cat. p 7.11, 7.13 |
| Housing distance B, from housing centre to the panel front (end) edge | **24 or 34 mm**, chosen with the bolt | cat. p 7.13, 7.18 |
| Housing for **19 mm** board (262.26.035) | depth **14.0 +0.5**, A = 9.5 | cat. p 7.13 |
| Housing for 18 mm board (262.26.034) | depth 13.5 +0.5, A = 9.0 | cat. p 7.13 |
| Housing for 16 mm board (262.26.033) | depth 12.5 +0.5, A = 8.0 | cat. p 7.13 |
| Housing with rim, 19 mm (262.25.035) | depth 14.5 ±0.5, A = 9.5 | cat. p 7.14 |
| Dim. A | half the board thickness (housing/bolt centre plane) | cat. p 7.18 |
| Bolt hole in the panel's front edge | **Ø7 or Ø8**, depending on the bolt. The C100 drawing shows Ø8 | cat. p 7.13, 7.18 |
| Bolt into the face of the mating panel | S100/M100/M200: **Ø5**, screw-in. S100 also comes for Ø3. C100: Ø8 or Ø10 | cat. p 7.17, 7.19, 7.20, 7.18 |
| S100 thread lengths (Ø5 hole) | 8 / 11 / 15 mm. M100/M200 thread is 8.5 | cat. p 7.17, 7.19 |
| Min board thickness | 12 mm | cat. p 7.11 |
| Tolerance absorbed | drill-hole error of **+1 / -0.5 mm** | cat. p 7.11 |
| Clamping travel | 3.2 mm closing, 2 mm tightening, 0.5 mm re-tightening; optimum at 165° | cat. p 7.11 |
| Hand tighten only | no power tools | cat. p 7.11 |

Generator (`params.json` > `korpus`):
- `minifix_hus_d` 15. **OK**.
- `minifix_hus_avstand` 24. **OK** (B24).
- `minifix_hus_dybde` **13.5**. **DISAGREE.** 13.5 is the depth for the 18 mm housing. The 19 mm housing needs **14.0 +0.5**, or 14.5 with a rim. 13.5 is only right if the 15/18 housing (262.26.034) is bought for 19 mm board, and then its A = 9.0 sits 0.5 mm off the centre plane.
- `minifix_bolt_d` 5. **OK** for S100/M200.
- `minifix_bolt_dybde` 11. Matches the S100 11 mm thread. Check it against the bolt actually bought.
- `minifix_kanthull_dybde` **34**, drilled Ø`plugg_d` = 8. **DISAGREE (consistency).**
  - With B = 24, the edge hole only needs to reach the housing. Its far wall is at 24 + 7.5 = 31.5 mm.
  - 34 looks like the B34 value, so it drills 2.5 mm past the housing bore.
  - Häfele gives no explicit number for the edge-hole depth.
- `minifix_inn_fra_kant` 50: **NOT FOUND**. Häfele gives no rule for distance along the edge.

## 3. Confirmat one-piece connector 7 x 50

Sources:
- Häfele UK TCH 2023, cat. p 13.37: `hafele-uk_23T13-37.pdf`. The neighbouring page 13.36 is also saved.
- Häfele UK Tools 2023, cat. p 2.76: `hafele-uk_23C2-76.pdf`

| Rule | Value | Where |
|---|---|---|
| 7 x 50, Ø10 head (264.42.190 / 264.43.194) | thread Ø7, core Ø4 to 4.6, head Ø10 | cat. p 13.37 |
| Pilot (blind) hole in the receiving edge | **Ø5** (Ø5.4 for the SW4-drilled variant 264.43.194) | cat. p 13.37 |
| Through hole in the attached panel | **Ø7**, countersink **Ø10** | cat. p 2.76, step drill 001.22.485 "for 38 and 50 mm" |
| Min edge distance / spacing | **NOT FOUND** in the Häfele catalogue | n/a |

Generator:
- Through hole Ø7, countersink Ø10 on the outside, edge pilot Ø5 x 36. **OK.** The screw enters 50 - 19 = 31 mm, so 36 is enough.
- `konfirmat_y` [28, -20]: no official rule found to check it against.

## 4. System 32 / general planning (Hettich, Häfele)

Sources:
- Hettich "Ratgeber Möbeltechnik" (DIY, de/en, 05-2021): https://diy.hettich.com/fileadmin/Media_Center/Catalogue/Ratgeber_Moebeltechnik_de_en_05-2021.pdf, saved as `hettich_Ratgeber_Moebeltechnik_de_en_05-2021.pdf`
- Häfele Unitool jig, cat. p 3.44: `hafele-uk_23C3-44.pdf`

| Rule | Value | Where |
|---|---|---|
| System 32 holes | Ø5, pitch 32 mm | Ratgeber p5 |
| Front hole line | 37 mm from the side front edge | Ratgeber p5; Häfele cat. p 3.44 |
| Rear hole line | 37 mm from the rear edge (Hettich). The Häfele jig uses 60 mm from the rear edge | Ratgeber p5; Häfele cat. p 3.44 |
| First and last hole of a line | same distance from the top edge and the bottom edge | Ratgeber p5 |

**NOT FOUND** from an official public source:
- drawer-box tolerances,
- drawer-bottom thickness vs drawer width,
- groove position or depth,
- wooden-dowel (Ø8) depth, edge distance and minimum spacing between bores.

Hettich's KA 4532 sheet gives only the clearance, depth and width limits listed in section 1. I tried the Häfele dowel pages and the Hettich TuI catalogue: the catalogue PDF returned 404, and the dowel pages have no drilling rules. `plugg_*`, `not_*`, `bunn_spill_per_side` and `min_kantavstand_hull` therefore have no manual to check against.

## 5. CNC: bits, melamine, hold-down

Sources:
- Amana feeds/speeds sheet "Solid Carbide Compression Spiral Router Bits" (v12): https://cdn.shopify.com/s/files/1/1558/5651/files/Solid-Carbide-Compression-Spirals-v12.pdf, saved as `amana_Solid-Carbide-Compression-Spirals-v12.pdf`. This is Amana's own sheet, served from the ToolsToday CDN.
- ShopBot "Holding Down Material for Cutting" (2016). The official URL https://www.shopbottools.com/ShopBotDocs/files/holdingdown.pdf no longer serves the PDF, so the official file was taken from web.archive.org and saved as `shopbot_holdingdown.pdf`.
- Bit geometry: amanatool.com returns 403 to scripts. Cutting lengths come from Amana's part names plus retailer spec listings (burnstools.com, cncrouterstore.ca). **They are not from an Amana datasheet. Verify them on the actual bit.**

| Rule | Value | Where |
|---|---|---|
| Amana 46170, 1/4" compression, 2 flutes | cutting length **7/8" = 22.2 mm**, upcut portion about **7 mm**, OAL 2-1/2" | part name; retailer spec (B1) |
| Amana 46180, 1/8" compression, 2 flutes, 1/8" shank | cutting length **13/16" = 20.6 mm**, upcut **7/32" = 5.6 mm** | part name; burnstools spec |
| Amana 46137/46139, 1/8" compression, 1 flute | cutting length 3/8" = 9.5 mm. **Cannot go through 19 mm** | part name |
| Feeds at 18,000 rpm, MDF/laminate, depth of cut 1 x D | 2-flute 1/8": 80 ipm (2030 mm/min), chipload .0022". 2-flute 1/4": 220 ipm (5590 mm/min), .0061" | Amana sheet, "2 Flute" table |
| Deeper passes | 2 x D: reduce feed 25%. 3 x D: reduce feed 50% | Amana sheet footnote |
| Compression first pass | must be deeper than the upcut portion, otherwise the top face chips | retailer guidance, not official |
| Small parts | can be thrown. Use tabs or an onion skin | ShopBot p8 |
| Onion skin | **0.010 to 0.030" (0.25 to 0.76 mm)**, depending on material and part size. Risky on uneven sheets or tables | ShopBot p8 |
| Adhesive / vacuum | small parts have too little area for vacuum and need extra hold-down | ShopBot p7 |

Generator (`verksted`):
- `fres_stor_skjaerlengde` 22.2. **OK** (46170).
- `fres_liten_skjaerlengde` **12.7**. **DISAGREE.** No Amana 1/8" compression bit has 12.7 mm. It is either 20.6 (46180) or 9.5 (46137/46139). The real value depends on which bit the makerspace has.
- `omganger_kontur` 2 (9.5 mm/pass) is deeper than the 7 mm upcut. **OK** for chipping. At about 1.5 x D, Amana says to cut feed about 25%. `mating_kontur` 4000 mm/min is within that.
- `mating_not` 3000 mm/min. If the groove is cut with the 1/8" bit, this is above Amana's 2030 mm/min.
- I did not check whether the generator emits tabs or an onion skin.

## 6. Edge banding

Sources:
- EGGER technical datasheet "ABS Edge Banding" (US, rev. 01, Dec 2020): https://www.egger.com/get_download/617d4359-b5bf-451a-8ade-c216e692fc1a/Technical_datasheet_Edging_ABS_en_US.pdf?country=US, saved as `egger_Technical_datasheet_Edging_ABS_en_US.pdf`
- Microvellum KB "Edgeband Premill Settings and Part Size Adjustment": https://intercom.help/microvellum-knowledge-base/en/articles/14858858-edgeband-premill-settings-and-part-size-adjustment, saved as `microvellum_edgeband-premill.html`
- The Mozaik KB article (https://mozaik.support.cyncly.com/hc/en-us/articles/43567545837585) is behind Cloudflare and was not saved. A search snippet showed a 400 mm finished part with 2 mm band on both long edges cut at 396.

| Rule | Value | Where |
|---|---|---|
| ABS thickness tolerance | 0 to 1.0 mm: +0.15/-0.10. 1.1 to 2.0 mm: +0.10/-0.20. 2.1 to 3.0 mm: +0.15/-0.25 | EGGER p2 "Tolerances" |
| ABS width tolerance | 12 to 54 mm: ±0.45 | EGGER p2 |
| Thickness range covered | up to 3.0 mm | EGGER p2/p3 |
| Standard thicknesses 0.4/0.8/1/2 | **NOT FOUND** as an official list. EGGER only gives ranges | n/a |
| Cabinet-software rule | cut size = finished size - band thickness on each banded edge + optional pre-mill / "part size adjustment" added back | Microvellum KB (legacy premill, and "Part Size Adjustment" section) |

Generator: **DISAGREE.** `params.json` has no edge-band thickness, and `kommode.py` lists banded edges ("Kantlist") without subtracting them from the cut size.
- Example: fronts banded on "alle 4 kanter" with 1 mm band grow 2 mm in each direction. That shrinks `fuge` 3 to 1 mm. With 2 mm band the fronts collide.
- This applies only if the dealer bands the parts after cutting them to the listed size.
