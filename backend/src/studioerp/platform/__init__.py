"""Platform ring (k1).

Inner ring built directly on the kernel. Holds shared identity entities
(``User``/``RefreshToken``), org structure (departments, org levels), the
key-value settings store and the in-app notifications inbox.

Only depends on ``studioerp`` (kernel). See ADR-0006 for why the User model
lives here instead of the people ring.
"""
