"""
Circular Restricted Three Body Problem Dynamics
"""
import numpy as np
from numba import njit

import pika.util as util
from pika.data import GRAV_PARAM
from pika.dynamics import AbstractDynamicsModel, VarGroups


class DynamicsModel(AbstractDynamicsModel):
    """
    CRTBP Dynamics Model

    Args:
        body1 (Body): one of the two primary bodies
        body2 (Body): the othe primary body

    The two bodies are stored in :attr:`bodies` in order of decreassing mass
    """

    def __init__(self, body1, body2):
        primary = body1 if body1.gm > body2.gm else body2
        secondary = body2 if body1.gm > body2.gm else body1
        totalGM = primary.gm + secondary.gm

        super().__init__(primary, secondary, mu=secondary.gm / totalGM)

        self._charL = secondary.sma
        self._charM = totalGM / GRAV_PARAM
        self._charT = np.sqrt(self._charL**3 / totalGM)

    @property
    def epochIndependent(self):
        return True

    def diffEqs(self, t, q, varGroups, params=None):
        return DynamicsModel._eoms(t, q, self._properties["mu"], varGroups)

    def bodyState(self, ix, t, params=None):
        if ix == 0:
            return np.asarray([-self._properties["mu"], 0.0, 0.0, 0.0, 0.0, 0.0])
        elif ix == 1:
            return np.asarray([1 - self._properties["mu"], 0.0, 0.0, 0.0, 0.0, 0.0])
        else:
            raise ValueError(f"Index {ix} must be zero or one")

    def stateSize(self, varGroups):
        varGroups = util.toList(varGroups)
        return 6 * (VarGroups.STATE in varGroups) + 36 * (VarGroups.STM in varGroups)

    def varNames(self, varGroups):
        if varGroups == VarGroups.STATE:
            return ["x", "y", "z", "dx", "dy", "dz"]
        else:
            return super().varNames(varGroups)  # defaults are fine for the rest

    @staticmethod
    @njit
    def _eoms(t, q, mu, varGroups):
        qdot = np.zeros(q.shape)

        # Pre-compute some values; multiplication is faster than exponents
        r13 = np.sqrt((q[0] + mu) * (q[0] + mu) + q[1] * q[1] + q[2] * q[2])
        r23 = np.sqrt((q[0] - 1 + mu) * (q[0] - 1 + mu) + q[1] * q[1] + q[2] * q[2])
        omm = 1 - mu
        r23_3 = r23 * r23 * r23
        r13_3 = r13 * r13 * r13

        # State variable derivatives
        qdot[:3] = q[3:6]
        qdot[3] = (
            2 * q[4] + q[0] - omm * (q[0] + mu) / r13_3 - mu * (q[0] - omm) / r23_3
        )
        qdot[4] = q[1] - 2 * q[3] - omm * q[1] / r13_3 - mu * q[1] / r23_3
        qdot[5] = -omm * q[2] / r13_3 - mu * q[2] / r23_3

        # Compute STM elements
        if VarGroups.STM in varGroups:
            r13_5 = r13_3 * r13 * r13
            r23_5 = r23_3 * r23 * r23

            # Compute the pseudopotential Jacobian
            #   U = [Uxx, Uyy, Uzz, Uxy, Uxz, Uyz]
            U = np.zeros((6,))

            U[0] = (
                1
                - omm / r13_3
                - mu / r23_3
                + 3 * omm * (q[0] + mu) * (q[0] + mu) / r13_5
                + 3 * mu * (q[0] - omm) * (q[0] - omm) / r23_5
            )
            U[1] = (
                1
                - omm / r13_3
                - mu / r23_3
                + 3 * omm * q[1] * q[1] / r13_5
                + 3 * mu * q[1] * q[1] / r23_5
            )
            U[2] = (
                -omm / r13_3
                - mu / r23_3
                + 3 * omm * q[2] * q[2] / r13_5
                + 3 * mu * q[2] * q[2] / r23_5
            )
            U[3] = (
                3 * omm * (q[0] + mu) * q[1] / r13_5
                + 3 * mu * (q[0] - omm) * q[1] / r23_5
            )
            U[4] = (
                3 * omm * (q[0] + mu) * q[2] / r13_5
                + 3 * mu * (q[0] - omm) * q[2] / r23_5
            )
            U[5] = 3 * omm * q[1] * q[2] / r13_5 + 3 * mu * q[1] * q[2] / r23_5

            # Compute STM derivative
            #   PhiDot = A * Phi
            #   q[6] through q[42] represent the STM (Phi) in row-major order

            # first three rows of PhiDot are the last three rows of Phi
            for r in range(3):
                for c in range(6):
                    qdot[6 + 6 * r + c] = q[6 + 6 * (r + 3) + c]

            for c in range(6):
                qdot[6 + 6 * 3 + c] = (
                    U[0] * q[6 + 6 * 0 + c]
                    + U[3] * q[6 + 6 * 1 + c]
                    + U[4] * q[6 + 6 * 2 + c]
                    + 2 * q[6 + 6 * 4 + c]
                )
                qdot[6 + 6 * 4 + c] = (
                    U[3] * q[6 + 6 * 0 + c]
                    + U[1] * q[6 + 6 * 1 + c]
                    + U[5] * q[6 + 6 * 2 + c]
                    - 2 * q[6 + 6 * 3 + c]
                )
                qdot[6 + 6 * 5 + c] = (
                    U[4] * q[6 + 6 * 0 + c]
                    + U[5] * q[6 + 6 * 1 + c]
                    + U[2] * q[6 + 6 * 2 + c]
                )

        # There are no epoch or parameter partials
        return qdot
