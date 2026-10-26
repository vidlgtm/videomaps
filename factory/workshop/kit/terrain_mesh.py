"""Pure-numpy assembly of the fly terrain as ONE mesh: the region at full detail, a coarse ring around it out to the
horizon (with a hole where the region is) and a stitched strip between the two borders, so there is no gap and no step.
Coordinates are region pixels (col, row) at the region zoom; the caller converts to world space and orients the faces."""
import numpy as np


def zipper(A, B):
    """A, B: [(vertex index, position along the side)] sorted by position -> triangles filling the strip between them"""
    i = j = 0
    out = []
    while i < len(A) - 1 or j < len(B) - 1:
        if j >= len(B) - 1 or (i < len(A) - 1 and A[i + 1][1] <= B[j + 1][1]):
            out.append((A[i][0], A[i + 1][0], B[j][0])); i += 1
        else:
            out.append((A[i][0], B[j + 1][0], B[j][0])); j += 1
    return out


def orient_up(co, faces):
    """flip the faces whose (x, y) winding is clockwise, so every normal points up (+z); co in world space"""
    faces = np.asarray(faces)
    if not len(faces): return faces
    a, b, c = co[faces[:, 0]], co[faces[:, 1]], co[faces[:, 2]]
    nz = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    faces = faces.copy()
    faces[nz < 0] = faces[nz < 0][:, ::-1]
    return faces


def assemble(W, H, step, far, sf, h_main, h_far):
    """W, H region size (px); far = {x0, x1, y0, y1}: ring extent in region px (x0 < 0 < W-1 < x1, same for y);
    sf ring spacing (px); h_main / h_far (cols, rows) -> heights (vectorised).
    returns co (n, 3) as [col, row, h], quads (m, 4), tris (k, 3)  (winding not yet oriented)"""
    xs = np.r_[np.arange(0, W - 1, step), W - 1].astype(np.float64)
    ys = np.r_[np.arange(0, H - 1, step), H - 1].astype(np.float64)
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys)
    vm = np.stack([X.ravel(), Y.ravel(), np.asarray(h_main(X, Y), np.float64).ravel()], 1)
    im = np.arange(nx * ny).reshape(ny, nx)
    qm = np.stack([im[:-1, :-1].ravel(), im[:-1, 1:].ravel(), im[1:, 1:].ravel(), im[1:, :-1].ravel()], 1)

    fxs = far["x0"] + sf * np.arange(int((far["x1"] - far["x0"]) // sf) + 1)
    fys = far["y0"] + sf * np.arange(int((far["y1"] - far["y0"]) // sf) + 1)
    i0 = int(np.searchsorted(fxs, 0.0, side="left") - 1)          # last ring line strictly left of the region
    i1 = int(np.searchsorted(fxs, W - 1.0, side="right"))         # first ring line strictly right of it
    j0 = int(np.searchsorted(fys, 0.0, side="left") - 1)
    j1 = int(np.searchsorted(fys, H - 1.0, side="right"))
    if not (0 <= i0 < i1 < len(fxs) and 0 <= j0 < j1 < len(fys)):
        raise ValueError("the coarse ring must surround the region on every side")
    FX, FY = np.meshgrid(fxs, fys)
    vf = np.stack([FX.ravel(), FY.ravel(), np.asarray(h_far(FX, FY), np.float64).ravel()], 1)
    jf = np.arange(len(fxs) * len(fys)).reshape(len(fys), len(fxs)) + len(vm)
    K, L = np.meshgrid(np.arange(len(fxs) - 1), np.arange(len(fys) - 1))
    keep = ~((K >= i0) & (K < i1) & (L >= j0) & (L < j1))
    K, L = K[keep], L[keep]
    qf = np.stack([jf[L, K], jf[L, K + 1], jf[L + 1, K + 1], jf[L + 1, K]], 1)

    tris = []
    tris += zipper([(jf[j0, k], fxs[k]) for k in range(i0, i1 + 1)], [(im[0, c], xs[c]) for c in range(nx)])
    tris += zipper([(jf[j1, k], fxs[k]) for k in range(i0, i1 + 1)], [(im[ny - 1, c], xs[c]) for c in range(nx)])
    tris += zipper([(jf[l, i0], fys[l]) for l in range(j0, j1 + 1)], [(im[r, 0], ys[r]) for r in range(ny)])
    tris += zipper([(jf[l, i1], fys[l]) for l in range(j0, j1 + 1)], [(im[r, nx - 1], ys[r]) for r in range(ny)])
    co = np.concatenate([vm, vf])
    return co, np.concatenate([qm, qf]), np.asarray(tris, np.int64)
