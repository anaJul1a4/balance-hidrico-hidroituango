"""Priority-Flood + épsilon (Barnes, Lehman & Mulla, 2014, Computers & Geosciences 62:117-127).

Rellena depresiones e impone una pendiente mínima `eps` sobre las zonas planas, de modo que
toda celda tenga un camino estrictamente descendente hacia el borde del DEM o hacia NoData.
"""
import heapq

import numba
import numpy as np


@numba.njit(cache=True)
def priority_flood_eps(z, nodata, eps):
    nr, nc = z.shape
    out = z.copy()
    closed = np.zeros((nr, nc), dtype=np.bool_)
    heap = [(0.0, 0, 0)]
    heap.pop()
    dr = np.array([-1, -1, 0, 1, 1, 1, 0, -1])
    dc = np.array([0, 1, 1, 1, 0, -1, -1, -1])
    for r in range(nr):
        for c in range(nc):
            if z[r, c] == nodata:
                closed[r, c] = True
                continue
            edge = r == 0 or c == 0 or r == nr - 1 or c == nc - 1
            if not edge:
                for k in range(8):
                    if z[r + dr[k], c + dc[k]] == nodata:
                        edge = True
                        break
            if edge:
                closed[r, c] = True
                heapq.heappush(heap, (out[r, c], r, c))
    while len(heap) > 0:
        h, r, c = heapq.heappop(heap)
        for k in range(8):
            rr, cc = r + dr[k], c + dc[k]
            if rr < 0 or cc < 0 or rr >= nr or cc >= nc or closed[rr, cc]:
                continue
            closed[rr, cc] = True
            if out[rr, cc] <= h:
                out[rr, cc] = h + eps
            heapq.heappush(heap, (out[rr, cc], rr, cc))
    return out


def condicionar(z, nodata=-9999.0, eps=1e-3):
    return priority_flood_eps(np.asarray(z, dtype=np.float64), float(nodata), float(eps))
