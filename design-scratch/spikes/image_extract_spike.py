"""Spike: extract product photos from catalog pages and link them to blocks.

Each catalog block (a heading + its table) carries a representative product photo, embedded
as a raster. This spike:
  - pulls embedded rasters per page (doc.extract_image),
  - filters out the recurring corner logo (right-margin) and tiny icons,
  - links each photo to the block it sits above (vertical proximity using block row bboxes),
  - saves the image to design-scratch/build/images/ and returns a block -> image map.

Honest scope: the link is **per block/family** (one representative photo shared by all SKUs
in the block), not per part number. Logo filtering is heuristic (right margin + min size).
Vector line-drawings (dimension diagrams) are not embedded rasters and aren't captured here.

Run: python design-scratch/spikes/image_extract_spike.py
"""
from __future__ import annotations

import os
import fitz  # pymupdf

IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "build", "images")


def page_images(pdf, page_no):
    """Embedded rasters on a page, filtered to likely product photos."""
    doc = fitz.open(pdf)
    page = doc[page_no - 1]
    W, H = page.rect.width, page.rect.height
    out, seen = [], set()
    for img in page.get_images(full=True):
        xref = img[0]
        if xref in seen:
            continue
        seen.add(xref)
        rects = page.get_image_rects(xref)
        if not rects:
            continue
        r = rects[0]
        info = doc.extract_image(xref)
        w, h = info["width"], info["height"]
        if r.x0 > 0.72 * W:            # right-margin corner logo/banner
            continue
        if w < 60 or h < 40:           # tiny icon
            continue
        out.append({
            "xref": xref, "ext": info["ext"], "bytes": info["image"], "w": w, "h": h,
            "bbox": (round(r.x0 / W, 4), round(r.y0 / H, 4), round(r.x1 / W, 4), round(r.y1 / H, 4)),
        })
    return out


def save_image(source, page_no, im):
    os.makedirs(IMG_DIR, exist_ok=True)
    name = f"{source}_p{page_no}_x{im['xref']}.{im['ext']}"
    with open(os.path.join(IMG_DIR, name), "wb") as f:
        f.write(im["bytes"])
    return f"images/{name}"            # relative to build/ (where product_db.json lives)


def link_images(pdf, page_no, blocks, source):
    """Assign each kept image to the block it sits above. Returns {block_index: image_entry}."""
    imgs = page_images(pdf, page_no)
    block_top = {}
    for bi, b in enumerate(blocks):
        ys = [row[2][1] for row in b["rows"] if row[2]]   # row bbox y0 (normalized)
        if ys:
            block_top[bi] = min(ys)
    res = {}
    for im in imgs:
        iy = im["bbox"][1]
        # prefer the block whose top is just below the image; else nearest by top
        below = [(bt - iy, bi) for bi, bt in block_top.items() if bt >= iy - 0.02]
        cands = below or [(abs(bt - iy), bi) for bi, bt in block_top.items()]
        if not cands:
            continue
        bi = min(cands)[1]
        res[bi] = {"path": save_image(source, page_no, im), "source": source,
                   "page": page_no, "bbox": im["bbox"], "scope": "block"}
    return res


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import table_extract_spike as tx
    for pno in (6, 45, 100):
        blocks = tx.parse_page(pno)
        linked = link_images(tx.PDF, pno, blocks, "wurth_b")
        print(f"B-{pno}: {len(page_images(tx.PDF, pno))} product images kept; "
              f"linked to {len(linked)} blocks")
        for bi, entry in sorted(linked.items()):
            fam = blocks[bi]["family"]
            print(f"   block {bi} ({fam}) <- {entry['path']}")
