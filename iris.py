"""Independent iris movement and a spiral-blade aperture renderer."""
import math
import pygame


class Iris:
    # Zero is fully open; one is fully closed. Gate shutdown does not reset it.
    def __init__(self):
        self.target_closed = False
        self.started = 0.0
        self.duration = 1.0
        self.initial = 0.0

    # Evaluate motion from elapsed time, allowing reversal without a position jump.
    def amount(self, now):
        t = max(0.0, min(1.0, (now-self.started)/self.duration))
        t = t*t*(3-2*t)
        return self.initial + ((1.0 if self.target_closed else 0.0)-self.initial)*t

    def set_closed(self, closed, now, duration=1.2):
        closed = bool(closed)
        if closed == self.target_closed:
            return False
        self.initial = self.amount(now)
        self.target_closed = closed
        self.started = now
        self.duration = max(.1, duration)
        return True

    # Shared blade boundaries avoid a different-looking first/last overlap.
    def draw(self, surface, center, radius, now, outline=(207, 216, 147)):
        amount = self.amount(now)
        if amount <= .0001:
            return
        layer = pygame.Surface((radius*2+1, radius*2+1), pygame.SRCALPHA)
        origin = (radius, radius)
        blade_count = 24
        sector = math.tau/blade_count
        aperture = round(radius*(1-amount))
        twist = -0.4
        pygame.draw.circle(layer, (48, 48, 48, 255), origin, radius)
        # Every blade uses the exact same curve, rotated by one sector. Draw
        # shared seams once so no final polygon can cover a neighboring blade.
        for blade in range(blade_count):
            base_angle = blade*sector - .3*amount
            edge = []
            for step in range(65):
                u = step/64
                r = radius+(aperture-radius)*u
                # Equal angular spacing makes blade width proportional to radius:
                # broad at the rim and narrow near the central opening.
                # Anchor curvature to the full iris radius, not the current
                # exposed annulus, so opening/closing never reshapes the taper.
                depth = 1-r/radius
                # A continuous sweeping arc matches the rotating blade edges
                # in the opening/closing references better than an S-shaped seam.
                theta = base_angle+twist*math.sin(depth*math.pi/2)
                edge.append((radius+r*math.cos(theta), radius+r*math.sin(theta)))
            pygame.draw.lines(layer, outline, False, edge, 1)
        # A single circular cutout keeps the inner edge round at every stage.
        if aperture >= 1:
            pygame.draw.circle(layer, (0, 0, 0, 0), origin, aperture)
            pygame.draw.circle(layer, outline, origin, aperture, 1)
        pygame.draw.circle(layer, outline, origin, radius, 1)
        surface.blit(layer, (center[0]-radius, center[1]-radius))
