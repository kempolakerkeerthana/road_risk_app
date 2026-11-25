"""Small distance helpers used by the location features (no extra library needed)."""
import math


def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two points on Earth, in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def along_route(plat, plon, alat, alon, blat, blon):
    """How far point P is from the straight route A->B (km), and how far along the route it lies (0 to 1)."""
    kx, ky = 111.32 * math.cos(math.radians(alat)), 110.57      # km per degree here
    px, py = (plon - alon) * kx, (plat - alat) * ky
    bx, by = (blon - alon) * kx, (blat - alat) * ky
    seg = bx * bx + by * by
    t = 0 if seg == 0 else max(0, min(1, (px * bx + py * by) / seg))
    return math.hypot(px - t * bx, py - t * by), t
