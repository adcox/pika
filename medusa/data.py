"""
Data
====

This module defines a few constants and the :class:`Body` class which stores data
about a celestial body (planet, moon, star, etc.)

.. autosummary::
   GRAV_PARAM
   G_MEAN_EARTH
   Body

Reference
---------

.. autodata:: GRAV_PARAM
.. autodata:: G_MEAN_EARTH

.. autoclass:: Body
   :members:

"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Union

from .util import float_eq

# ------------------------------------------------------------------------------
# Constants

GRAV_PARAM = 6.67384e-20
""": Universal gravitational constant (km**3/kg-s**2)"""

G_MEAN_EARTH = 9.80665e-3
""": Mean Earth gravity (km/s**2)"""


class Body:
    """
    Describe a celestial body (star, planet, moon)

    Args:
        name: Body name
        gm: gravitational parameter (km**2/sec**3)
        sma: orbital semimajor axis (km)
        ecc: orbital eccentricity
        inc: orbital inclination w.r.t. Earth Equatorial J2000 (deg)
        raan: right ascenscion of the ascending node w.r.t.
            Earth Equatorial J2000 (deg)
        spiceId: SPICE ID for this body
        parentId: SPICE ID for the body this body orbits. Set to
            ``None`` if there is no parent body
    """

    def __init__(
        self,
        name: str,
        gm: float,
        sma: float = 0.0,
        ecc: float = 0.0,
        inc: float = 0.0,
        raan: float = 0.0,
        spiceId: int = 0,
        parentId: Union[int, None] = None,
    ) -> None:
        #: Body name
        self.name = name

        #: Gravitational parameter (km**2/sec**3)
        self.gm = float(gm)

        #: orbital semimajor axis (km)
        self.sma = float(sma)

        #: orbital eccentricity
        self.ecc = float(ecc)

        #: orbital inclination w.r.t. Earth equatorial J2000 (deg)
        self.inc = float(inc)

        #: right ascension of the ascending node w.r.t. Earth equatorial J2000 (deg)
        self.raan = float(raan)

        #: SPICE ID for this body
        self.id = int(spiceId)

        #: SPICE ID for body this one orbits; set to ``None`` if there is no parent
        self.parentId = parentId

    @staticmethod
    def fromXML(file: str, name: str) -> Body:
        """
        Create a body from an XML file

        Args:
            file: path to the XML file
            name: Body name

        Returns:
            the corresponding data in a :class:`Body` object. If no body
            can be found that matches ``name``, ``None`` is returned.
        """
        tree = ET.parse(file)
        root = tree.getroot()

        def _expect(data: ET.Element, key: str) -> str:
            # Get value from data element, raise exception if it isn't there
            obj = data.find(key)
            if obj is None:
                raise RuntimeError(f"Could not read '{key}' for {name}")
            else:
                return str(obj.text)

        for data in root.iter("body"):
            obj = data.find("name")
            if obj is None:
                continue

            _name = obj.text
            if _name == name:
                try:
                    pid = int(data.find("parentId").text)  # type: ignore
                except:
                    pid = None

                return Body(
                    name,
                    float(_expect(data, "gm")),
                    sma=float(_expect(data, "circ_r")),
                    ecc=0.0,  # TODO why is this not read from data??
                    inc=float(_expect(data, "inc")),
                    raan=float(_expect(data, "raan")),
                    spiceId=int(_expect(data, "id")),
                    parentId=pid,
                )

        raise RuntimeError(f"Cannot find a body named {name}")

    def __eq__(self, other):
        if not isinstance(other, Body):
            return False

        return (
            self.name == other.name
            and float_eq(self.gm, other.gm)
            and float_eq(self.sma, other.sma)
            and float_eq(self.ecc, other.ecc)
            and float_eq(self.inc, other.inc)
            and float_eq(self.raan, other.raan)
            and self.id == other.id
            and self.parentId == other.parentId
        )

    def __repr__(self):
        vals = ", ".join(
            [
                "{!s}={!r}".format(lbl, getattr(self, lbl))
                for lbl in ("gm", "sma", "ecc", "inc", "raan", "id", "parentId")
            ]
        )
        return "<Body {!s}: {!s}>".format(self.name, vals)
